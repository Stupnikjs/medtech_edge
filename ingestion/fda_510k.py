"""
Ingestion openFDA - Device 510(k) Clearances
===========================================

Source : https://api.fda.gov/device/510k.json
Doc    : https://open.fda.gov/apis/device/510k/

Récupère les décisions de clearance 510(k) de la FDA (dispositifs médicaux)
et les exporte en CSV / JSON, et optionnellement en SQLite (--db).

Usage :
    python fda_510k_ingestion.py --start-date 2024-01-01 --end-date 2026-08-01
    python fda_510k_ingestion.py --applicant "Medtronic"
    python fda_510k_ingestion.py --product-code QKQ --limit 500 --db ../medtech.sqlite3
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # pour importer storage.db

from ingestion import open_fda as client
from storage import db

BASE_URL = "https://api.fda.gov/device/510k.json"
SOURCE = "openFDA_510k"
RECORD_NUMBER_FIELD = "k_number"

FIELDS_OF_INTEREST = [
    "k_number",
    "device_name",
    "applicant",
    "decision_date",
    "decision_description",
    "decision_code",
    "clearance_type",
    "product_code",
    "advisory_committee",
    "advisory_committee_description",
    "third_party_flag",
    "statement_or_summary",
    "type",
    "review_advisory_committee",
    "expedited_review_flag",
]


def extract_record(raw: dict) -> dict:
    return {field: raw.get(field, "") for field in FIELDS_OF_INTEREST}


def build_search_query(args: argparse.Namespace) -> str | None:
    clauses = []
    if args.applicant:
        clauses.append(f'applicant:"{args.applicant}"')
    if args.product_code:
        clauses.append(f'product_code:"{args.product_code}"')
    if args.advisory_committee:
        clauses.append(f'advisory_committee:"{args.advisory_committee}"')

    date_clause = client.build_date_clause(args.start_date, args.end_date)
    if date_clause:
        clauses.append(date_clause)

    return "+AND+".join(clauses) if clauses else None


def main():
    parser = argparse.ArgumentParser(description="Ingestion openFDA Device 510(k)")
    parser.add_argument("--start-date", help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--applicant", help="Nom de l'entreprise soumissionnaire")
    parser.add_argument("--product-code", help="Code produit FDA (ex: QKQ)")
    parser.add_argument("--advisory-committee", help="Code comité consultatif (ex: cv, ho, ne)")
    parser.add_argument("--limit", type=int, default=1000, help="Nombre max d'enregistrements (0 = tout, prudence)")
    parser.add_argument("--api-key", default=None, help="Clé API openFDA (optionnelle)")
    parser.add_argument("--output", default="fda_510k_export", help="Nom de fichier de sortie (sans extension)")
    parser.add_argument("--db", default=None, help="Chemin sqlite pour écrire aussi les records (optionnel)")
    args = parser.parse_args()

    search = build_search_query(args)
    records = client.fetch_all(BASE_URL, search, args.limit, args.api_key, extract_record)

    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    client.save_csv(records, out_dir / f"{args.output}.csv", FIELDS_OF_INTEREST)
    client.save_json(records, out_dir / f"{args.output}.json")

    if args.db:
        conn = db.init_db(args.db)
        # applicant -> applicant_raw pour coller au schema commun
        normalized = [{**r, "applicant_raw": r.get("applicant", "")} for r in records]
        n = db.insert_raw_records(conn, normalized, SOURCE, RECORD_NUMBER_FIELD)
        print(f"SQLite : {n} records upsertes dans {args.db} (source={SOURCE})")
        conn.close()


if __name__ == "__main__":
    main()