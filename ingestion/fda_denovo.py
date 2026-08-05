"""
Ingestion openFDA - Device De Novo
==================================

Source (attendue) : https://api.fda.gov/device/denovo.json
Doc                : https://open.fda.gov/apis/device/denovo/

Les demandes De Novo concernent des dispositifs sans predicat existant,
que la FDA classe directement en classe I ou II (au lieu du chemin 510k
classique). Interessant pour ton use case : ce sont souvent des devices
plus "nouveaux"/differencies que les 510k standards.

ATTENTION - a verifier avant un run en prod :
Je n'ai pas reussi a confirmer la liste exacte des champs via la doc live
pendant que j'ecrivais ce fichier (recherche web incomplete sur cet
endpoint precis, contrairement au 510k et au pma que j'ai pu confirmer).
Les noms de champs ci-dessous (device_name, applicant, decision_date,
decision_code, product_code, regulation_number, review_advisory_committee,
denovo_number) viennent de ma connaissance generale du schema openFDA et
PEUVENT etre legerement faux (ex: le nom du numero de dossier pourrait
etre "denovo_number" ou autre chose). Avant de lancer un vrai fetch,
verifie avec :
    curl "https://api.fda.gov/device/denovo.json?limit=1"
et ajuste FIELDS_OF_INTEREST / RECORD_NUMBER_FIELD en consequence -
c'est un changement d'une ligne, pas une refonte.

Usage :
    python fda_denovo_ingestion.py --start-date 2024-01-01 --end-date 2026-08-01
    python fda_denovo_ingestion.py --applicant "Butterfly Network" --db ../medtech.sqlite3
"""


import argparse
from datetime import datetime
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import RawClearanceRecord 
from storage.db import init_db, insert_raw_records



SOURCE = "openFDA_denovo"
RECORD_NUMBER_FIELD = "denovo_number"  # A VERIFIER (voir note en tete de fichier)

FIELDS_OF_INTEREST = [
    "denovo_number",
    "device_name",
    "applicant",
    "decision_date",
    "decision_code",           # attendu : "GRANT" / "DENY"
    "product_code",
    "regulation_number",
    "review_advisory_committee",
    "advisory_committee_description",
    "expedited_review_flag",
    "type",
    "decision_memo_url",
]

def parse_date(date_str: str) -> Optional[datetime.date]:
    """Convertit une chaîne au format MM/DD/YYYY en objet date."""
    if not date_str or not date_str.strip():
        return None
    try:
        return datetime.strptime(date_str.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


def parse_line_to_raw_record(
    line: str, source: str = "openFDA_510k"
) -> Optional[RawClearanceRecord]:
    """Transforme une ligne délimitée par '|' en une instance de RawClearanceRecord."""
    fields = [f.strip() for f in line.split("|")]

    # Vérification minimale du nombre de colonnes (au moins 22 colonnes)
    if len(fields) < 22:
        return None

    # Extraction sécurisée des dates et champs
    decision_date = parse_date(fields[11])  # DECISIONDATE (index 11)

    return RawClearanceRecord(
        k_number=fields[0],  # KNUMBER
        device_name=fields[21],  # DEVICENAME
        applicant_raw=fields[1],  # APPLICANT
        decision_date=decision_date,
        decision_code=fields[12],  # DECISION
        clearance_type=fields[18],  # TYPE
        product_code=fields[14],  # PRODUCTCODE
        advisory_committee=fields[16],  # CLASSADVISECOMM
        source=source,
    )


def process_raw_data(
    raw_data: str, source: str = "openFDA_510k"
) -> List[RawClearanceRecord]:
    """Parse l'ensemble du bloc de texte et retourne une liste d'objets RawClearanceRecord."""
    records = []
    lines = raw_data.strip().splitlines()

    # Si la première ligne contient les en-têtes (KNUMBER|APPLICANT|...), on la saute
    if lines and lines[0].startswith("KNUMBER"):
        lines = lines[1:]

    for line in lines:
        if line.strip():
            record = parse_line_to_raw_record(line, source=source)
            if record:
                records.append(record)

    return records


# ==========================================
# EXÉCUTION & TEST SUR VOS DONNÉES
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestion openFDA Device PMA")
    parser.add_argument("--db", default=None, help="Chemin sqlite pour écrire aussi les records (optionnel)")
    parser.add_argument("--file", default=None, required=True, help="path to csv denovo files")
    donnees_test = """KNUMBER|APPLICANT|CONTACT|STREET1|STREET2|CITY|STATE|COUNTRY_CODE|ZIP|POSTAL_CODE|DATERECEIVED|DECISIONDATE|DECISION|REVIEWADVISECOMM|PRODUCTCODE|STATEORSUMM|CLASSADVISECOMM|SSPINDICATOR|TYPE|THIRDPARTY|EXPEDITEDREVIEW|DEVICENAME
DEN000001|Ohmeda Medical|DANIEL  KOSEDNAR|P.O. Box 7550||Madison|WI|US|53707|53707|01/07/2000|01/11/2000|DENG|AN|MRN||AN||Post-NSE|N||OHMEDA INOVENT DELIVERY SYSTEM
K000001|Boston Scientific Scimed, Inc.|RON  BENNETT|5905 Nathan Ln.||Plymouth|MN|US|55442|55442|01/03/2000|06/05/2000|SESE|SU|JCT|Summary|SU||Traditional|N||WALLGRAFT TRACHEOBRONCHIAL ENDOPROSTHESIS AND UNISTEP DELIVERY SYSTEM"""
    args = parser.parse_args()
    # Traitement des données
    liste_records = process_raw_data(donnees_test, source="openFDA_510k")
    if args.db:
        conn = init_db(args.db)
        # Affichage des résultats
        print(f"Nombre d'enregistrements créés : {len(liste_records)}\n")
        insert_raw_records(conn=conn, records=liste_records, source=SOURCE, record_number_field=RECORD_NUMBER_FIELD)
    