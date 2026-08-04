"""
Ingestion openFDA - Device PMA (Premarket Approval)
===================================================

Source : https://api.fda.gov/device/pma.json
Doc    : https://open.fda.gov/apis/device/pma/

Couvre les dispositifs de classe III (risque le plus eleve), a la fois
les PMA originales et les supplements post-approbation. decision_code
distingue le type de décision (ex: APPR = approved).

Champs confirmes le 2026-08-02 via un appel reel (curl .../pma.json?limit=1) :
pas de champ `type` au niveau racine (contrairement a ce que je supposais
au depart) ; `device_class` existe mais est niche sous `openfda.device_class`,
pas a la racine -- traite a part dans extract_record.

Usage :
    python fda_pma_ingestion.py --start-date 2024-01-01 --end-date 2026-08-01
    python fda_pma_ingestion.py --applicant "Penumbra" --db ../medtech.sqlite3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion import open_fda as client
from storage import db

BASE_URL = "https://api.fda.gov/device/pma.json"
SOURCE = "openFDA_pma"
RECORD_NUMBER_FIELD = "pma_number"

FIELDS_OF_INTEREST = [
    "pma_number",
    "supplement_number",
    "trade_name",          # equivalent de device_name pour le 510k
    "generic_name",
    "applicant",
    "decision_date",
    "decision_code",
    "ao_statement",
    "product_code",
    "advisory_committee",
    "advisory_committee_description",
    "supplement_type",     # utilise comme equivalent de clearance_type
    "supplement_reason",
    "expedited_review_flag",
    "date_received",
    "docket_number",
    "city",
    "state",
]


def extract_record(raw: dict) -> dict:
    record = {field: raw.get(field, "") for field in FIELDS_OF_INTEREST}
    # normalisation pour coller au schema commun (device_name / clearance_type)
    record["device_name"] = record.get("trade_name", "")
    record["clearance_type"] = record.get("supplement_type") or "Original PMA"
    # device_class est niche sous openfda, pas a la racine du record
    record["device_class"] = raw.get("openfda", {}).get("device_class", "")
    return record


def build_search_query(args: argparse.Namespace) -> str | None:
    clauses = []
    if args.applicant:
        clauses.append(f'applicant:"{args.applicant}"')
    if args.product_code:
        clauses.append(f'product_code:"{args.product_code}"')
    if args.advisory_committee:
        clauses.append(f'advisory_committee:"{args.advisory_committee}"')
    if args.decision_code:
        clauses.append(f'decision_code:"{args.decision_code}"')

    date_clause = client.build_date_clause(args.start_date, args.end_date)
    if date_clause:
        clauses.append(date_clause)

    return "+AND+".join(clauses) if clauses else None


def main():
    parser = argparse.ArgumentParser(description="Ingestion openFDA Device PMA")
    parser.add_argument("--start-date", help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--applicant", help="Nom de l'entreprise soumissionnaire")
    parser.add_argument("--product-code", help="Code produit FDA")
    parser.add_argument("--advisory-committee", help="Code comité consultatif (ex: cv, ho, ne)")
    parser.add_argument("--decision-code", help='Code decision (ex: "APPR")')
    parser.add_argument("--limit", type=int, default=1000, help="Nombre max d'enregistrements (0 = tout, prudence)")
    parser.add_argument("--api-key", default=None, help="Clé API openFDA (optionnelle)")
    parser.add_argument("--output", default="fda_pma_export", help="Nom de fichier de sortie (sans extension)")
    parser.add_argument("--db", default=None, help="Chemin sqlite pour écrire aussi les records (optionnel)")
    args = parser.parse_args()

    search = build_search_query(args)
    records = client.fetch_all(BASE_URL, search, args.limit, args.api_key, extract_record)

    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    csv_fields = FIELDS_OF_INTEREST + ["device_name", "clearance_type", "device_class"]
    client.save_csv(records, out_dir / f"{args.output}.csv", csv_fields)
    client.save_json(records, out_dir / f"{args.output}.json")

    if args.db:
        conn = db.init_db(args.db)
        normalized = [{**r, "applicant_raw": r.get("applicant", "")} for r in records]
        n = db.insert_raw_records(conn, normalized, SOURCE, RECORD_NUMBER_FIELD)
        print(f"SQLite : {n} records upsertes dans {args.db} (source={SOURCE})")
        conn.close()


if __name__ == "__main__":
    main()