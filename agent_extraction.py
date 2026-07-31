"""
Agent d'extraction : lit un DocumentBrut, en sort un EtudeExtraite validé.

Découplé du provider LLM via litellm — un seul point de config (EXTRACTION_MODEL)
pour switcher de modèle sans toucher au reste du pipeline.

Installation : pip install litellm --break-system-packages
"""
from dotenv import load_dotenv


import os
import json
import logging

import litellm
from litellm import completion

from models.schemas import DocumentBrut, EtudeExtraite


load_dotenv()
logger = logging.getLogger(__name__)

# Seul endroit à changer pour switcher de modèle/provider.
# Format litellm : "provider/nom_du_modele"
# ex: "anthropic/claude-sonnet-4-5", "openai/gpt-5", "gemini/gemini-2.5-pro"
# Défaut : Gemini 2.5 Flash — tier gratuit (250 req/jour), aucune carte requise.
# Nécessite GEMINI_API_KEY (récupérable sur https://aistudio.google.com).
EXTRACTION_MODEL = os.environ.get("EXTRACTION_MODEL", "gemini/gemini-1.5-flash")

# Seuil sous lequel on flague l'extraction pour review humaine plutôt que
# de l'insérer directement en base. À ajuster selon tes retours terrain.
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
- type_etude doit être choisi parmi : rct, observationnelle, meta_analyse,
  preclinique, autre — en te basant sur le design décrit, pas sur le sujet.

Réponds UNIQUEMENT avec un objet JSON valide correspondant au schéma, sans
texte avant ou après, sans balises markdown."""


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
            temperature=0,  # extraction factuelle, pas de créativité
        )
    except litellm.exceptions.APIError as e:
        logger.warning(f"Erreur API LLM ({EXTRACTION_MODEL}) pour '{document.titre[:50]}' : {e}")
        return None

    contenu = response.choices[0].message.content

    try:
        donnees = json.loads(contenu)
        etude = EtudeExtraite(**donnees)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"Sortie LLM invalide pour '{document.titre[:50]}' : {e}")
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