"""
Agent d'extraction : lit un DocumentBrut, en sort un EtudeExtraite validé.

Découplé du provider LLM via litellm — un seul point de config (EXTRACTION_MODEL)
pour switcher de modèle sans toucher au reste du pipeline.

Installation : pip install litellm --break-system-packages
"""
from dotenv import load_dotenv

import os
import json
import re
import logging

import litellm
from litellm import completion

from models.schemas import DocumentBrut, EtudeExtraite


load_dotenv()
logger = logging.getLogger(__name__)

# Seul endroit à changer pour switcher de modèle/provider.
# Format litellm : "provider/nom_du_modele"
EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "gemini/gemini-2.0-flash")

SEUIL_CONFIANCE_MIN = 0.6

PROMPT_SYSTEME = """Tu es un analyste spécialisé en essais cliniques pharmaceutiques.
Tu reçois un abstract scientifique et tu dois en extraire les données structurées
définies par le schéma JSON fourni.

Règles strictes :
- N'invente JAMAIS une donnée absente du texte. Si une information n'est pas
  explicitement dans l'abstract, mets null pour ce champ.
- confiance_extraction doit refléter honnêtement ta certitude globale sur
  l'ensemble des champs extraits, pas juste sur un seul champ.
- raisonnement doit expliquer brièvement d'où viennent les valeurs principales
  (phase, endpoint, p-value) et signaler toute ambiguïté rencontrée.
- type_etude doit être choisi parmi les valeurs autorisées du schéma, en te
  basant sur le design décrit, pas sur le sujet.

Réponds UNIQUEMENT avec un objet JSON valide correspondant au schéma, sans
texte avant ou après, sans balises markdown."""


def _nettoyer_json(contenu: str) -> str:
    """
    Filet de sécurité : certains modèles ajoutent des balises markdown
    (```json ... ```) malgré la consigne de ne pas le faire. On les retire
    si présentes, sans planter si elles sont absentes.
    """
    contenu = contenu.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", contenu, re.DOTALL)
    return match.group(1) if match else contenu


def extraire_etude(document: DocumentBrut) -> EtudeExtraite | None:
    """
    Envoie le texte_brut d'un DocumentBrut au LLM configuré et retourne
    un EtudeExtraite validé, ou None si l'extraction échoue.
    """
    schema = EtudeExtraite.model_json_schema()

    prompt_utilisateur = f"""Schéma JSON attendu :
{json.dumps(schema, ensure_ascii=False, indent=2)}

Titre : {document.titre}

Abstract :
{document.texte_brut}"""

    try:
        response = completion(
            model=EXTRACTION_MODEL,
            messages=[
                {"role": "system", "content": PROMPT_SYSTEME},
                {"role": "user", "content": prompt_utilisateur},
            ],
            temperature=0,
            response_format={"type": "json_object"},  # force le mode JSON natif du provider
        )
    except litellm.exceptions.AuthenticationError as e:
        logger.error(f"Clé API invalide/absente pour {EXTRACTION_MODEL} : {e}")
        return None
    except litellm.exceptions.RateLimitError as e:
        logger.warning(f"Rate limit atteint pour {EXTRACTION_MODEL} : {e}")
        return None
    except litellm.exceptions.BadRequestError as e:
        # Souvent déclenché si le modèle ne supporte PAS response_format=json_object
        logger.error(
            f"Requête invalide pour {EXTRACTION_MODEL} (le modèle supporte-t-il "
            f"response_format json_object ?) : {e}"
        )
        return None
    except Exception as e:
        logger.error(f"Erreur inattendue LLM ({EXTRACTION_MODEL}) pour '{document.titre[:50]}' : {e}")
        return None

    contenu = response.choices[0].message.content
    contenu_nettoye = _nettoyer_json(contenu)

    try:
        donnees = json.loads(contenu_nettoye)
    except json.JSONDecodeError as e:
        logger.warning(
            f"JSON invalide pour '{document.titre[:50]}' : {e}\n"
            f"Contenu brut reçu : {contenu[:300]}"
        )
        return None

    try:
        etude = EtudeExtraite(**donnees)
    except Exception as e:
        # Erreur de validation Pydantic — le JSON est valide mais ne respecte
        # pas le schéma (champ manquant, mauvais type...)
        logger.warning(
            f"Validation Pydantic échouée pour '{document.titre[:50]}' : {e}\n"
            f"Données reçues : {donnees}"
        )
        return None

    if etude.confiance_extraction < SEUIL_CONFIANCE_MIN:
        logger.info(
            f"Confiance basse ({etude.confiance_extraction}) pour '{document.titre[:50]}' "
            f"— à envoyer en review humaine plutôt qu'insertion directe."
        )

    return etude


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from parse_pubmed import pipeline_pubmed

    docs = pipeline_pubmed("GLP-1 receptor agonist diabetes phase 3", max_resultats=2)
    for doc in docs:
        etude = extraire_etude(doc)
        if etude:
            print(f"\n--- {doc.titre[:60]} ---")
            print(etude.model_dump_json(indent=2))
        else:
            print(f"\n--- ÉCHEC extraction : {doc.titre[:60]} ---")
