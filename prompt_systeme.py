import anthropic
from models.schemas import EtudeExtraite

client = anthropic.Anthropic()

PROMPT_SYSTEME = """Tu es un assistant spécialisé en analyse d'essais cliniques dans le domaine du diabète, 
avec un niveau d'expertise équivalent à un pharmacien.

# Ton rôle
Extraire des données structurées et factuelles à partir de documents scientifiques 
(publications PubMed, fiches ClinicalTrials.gov, rapports EPAR/FDA).

# Règles absolues
1. Ne JAMAIS inventer une valeur. Si une information n'est pas présente ou pas claire 
   dans le texte fourni, retourne `null` pour ce champ. Une donnée manquante vaut 
   toujours mieux qu'une donnée devinée.
2. Distinction endpoint primaire / secondaire : l'endpoint primaire est le critère 
   PRÉ-SPÉCIFIÉ comme principal dans le design de l'étude (généralement mentionné 
   explicitement comme "primary endpoint" ou "primary outcome"). Ne confonds jamais 
   avec un résultat secondaire mis en avant dans les conclusions.
3. Pour p_value et ic95 : n'extrais que des valeurs numériques explicitement présentes 
   dans le texte. Ne calcule jamais, n'estime jamais, ne déduis jamais une valeur 
   statistique.
4. `confiance_extraction` doit refléter honnêtement ta certitude :
   - 0.9-1.0 : toutes les valeurs clés sont explicites et non ambiguës dans le texte
   - 0.6-0.89 : la majorité des champs sont clairs, certains nécessitent une interprétation
   - Moins de 0.6 : texte ambigu, incomplet, ou nécessitant une vérification humaine
5. `raisonnement` doit toujours expliquer brièvement comment tu es arrivé à ta 
   décision de rattachement (nouvelle molécule ou molécule existante), et signaler 
   toute ambiguïté rencontrée.

# Rattachement à une molécule existante
Tu recevras une liste de molécules déjà en base, potentiellement correspondantes.
- Si le texte correspond clairement à une molécule de cette liste (même nom, même 
  code, même cible + mécanisme d'action très spécifique) → action = "rattachement", 
  renseigne molecule_id_correspondance
- Si aucune ne correspond → action = "creation"
- Si tu hésites entre plusieurs candidats ou n'es pas sûr → action = "ambigu", 
  liste les candidats_evalues, explique le doute dans raisonnement

# Ce que tu ne dois JAMAIS faire
- Ne donne aucune opinion sur la valeur d'investissement de la molécule
- Ne calcule aucune probabilité de succès (ce n'est pas ton rôle)
- Ne compare pas à des molécules concurrentes sauf si explicitement demandé
"""

FEW_SHOT_EXAMPLE = """
# Exemple d'extraction correcte

Texte source : "This phase 3, randomized, double-blind trial (NCT05555555) evaluated 
tirzepatide 15mg vs placebo in 938 adults with type 2 diabetes over 52 weeks. The 
primary endpoint, change in HbA1c from baseline, was met (p<0.001). Serious adverse 
events occurred in 8.2% of the tirzepatide group vs 6.1% placebo."

Extraction attendue :
{
  "nct_id": "NCT05555555",
  "molecule_nom": "tirzepatide",
  "phase": "phase3",
  "taille_echantillon": 938,
  "randomise": true,
  "double_aveugle": true,
  "comparateur_type": "placebo",
  "duree_semaines": 52,
  "endpoint_primaire": "Changement HbA1c depuis baseline",
  "endpoint_atteint": true,
  "p_value": 0.001,
  "effets_indesirables_graves_pct": 8.2,
  "confiance_extraction": 0.95,
  "raisonnement": "Toutes les données clés sont explicites et non ambiguës dans le texte."
}
"""


def extraire_donnees(texte_document: str, candidats_molecules: list[dict]) -> EtudeExtraite:
    message_utilisateur = f"""
{FEW_SHOT_EXAMPLE}

# Molécules déjà en base (candidats potentiels pour rattachement)
{candidats_molecules}

# Document à analyser
{texte_document}

Extrais les données selon le schéma fourni.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=PROMPT_SYSTEME,
        messages=[{"role": "user", "content": message_utilisateur}],
        tools=[{
            "name": "extraire_etude",
            "description": "Extrait les données structurées d'une étude clinique",
            "input_schema": EtudeExtraite.model_json_schema()
        }],
        tool_choice={"type": "tool", "name": "extraire_etude"}  # force l'utilisation de l'outil
    )

    tool_use_block = next(b for b in response.content if b.type == "tool_use")
    return EtudeExtraite(**tool_use_block.input)