"""
Parsing ClinicalTrials.gov — API v2, pas de clé requise.
Installation : pip install requests --break-system-packages
"""

import requests
from typing import List
from  import DocumentBrut, TypeSource

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def rechercher_essais(condition: str, phases: list[str], statuts: list[str], max_resultats: int = 20) -> list[dict]:
    """Interroge l'API et retourne les études brutes (JSON)."""
    params = {
        "query.cond": condition,
        "filter.phase": ",".join(phases),          # ex: ["PHASE2", "PHASE3"]
        "filter.overallStatus": ",".join(statuts),  # ex: ["RECRUITING", "COMPLETED"]
        "pageSize": max_resultats,
    }
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("studies", [])


def parser_essai(etude_json: dict) -> DocumentBrut | None:
    """Convertit une étude brute de l'API en DocumentBrut."""
    try:
        protocole = etude_json["protocolSection"]
        identification = protocole["identificationModule"]
        description = protocole.get("descriptionModule", {})

        nct_id = identification["nctId"]
        titre = identification["briefTitle"]
        resume = description.get("briefSummary", "")
        detail = description.get("detailedDescription", "")
        texte_brut = f"{resume}\n\n{detail}".strip()

        if len(texte_brut) < 50:
            return None

        return DocumentBrut(
            type_source=TypeSource.clinicaltrials,
            url=f"https://clinicaltrials.gov/study/{nct_id}",
            titre=titre,
            texte_brut=texte_brut,
            date_publication=None,
            payload_brut=etude_json,
        )
    except KeyError:
        return None


def pipeline_clinicaltrials(condition: str, phases: list[str], statuts: list[str], max_resultats: int = 20) -> List[DocumentBrut]:
    """Point d'entrée : recherche + parse une liste d'essais."""
    essais_bruts = rechercher_essais(condition, phases, statuts, max_resultats)
    documents = []
    for essai in essais_bruts:
        doc = parser_essai(essai)
        if doc:
            documents.append(doc)
    return documents


if __name__ == "__main__":
    docs = pipeline_clinicaltrials(
        condition="diabetes",
        phases=["PHASE2", "PHASE3"],
        statuts=["RECRUITING", "ACTIVE_NOT_RECRUITING"],
        max_resultats=10,
    )
    for d in docs:
        print(d.titre[:80], "-", len(d.texte_brut), "caractères")