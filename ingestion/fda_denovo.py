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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion import openfda_client as client
from storage import db

BASE_URL = "https://api.fda.gov/device/denovo.json"
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


def extract_record(raw: dict) -> dict:
    record = {field: raw.get(field, "") for field in FIELDS_OF_INTEREST}
    record["advisory_committee"] = record.get("review_advisory_committee", "")
    record["clearance_type"] = "De Novo"
    return record


def build_search_query(args: argparse.Namespace) -> str | None:
    clauses = []
    if args.applicant:
        clauses.append(f'applicant:"{args.applicant}"')
    if args.product_code:
        clauses.append(f'product_code:"{args.product_code}"')
    if args.advisory_committee:
        clauses.append(f'review_advisory_committee:"{args.advisory_committee}"')

    date_clause = client.build_date_clause(args.start_date, args.end_date)
    if date_clause:
        clauses.append(date_clause)

    return "+AND+".join(clauses) if clauses else None


def main():
    parser = argparse.ArgumentParser(description="Ingestion openFDA Device De Novo")
    parser.add_argument("--start-date", help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--applicant", help="Nom de l'entreprise soumissionnaire")
    parser.add_argument("--product-code", help="Code produit FDA")
    parser.add_argument("--advisory-committee", help="Code comité consultatif (ex: cv, ho, ne)")
    parser.add_argument("--limit", type=int, default=1000, help="Nombre max d'enregistrements (0 = tout, prudence)")
    parser.add_argument("--api-key", default=None, help="Clé API openFDA (optionnelle)")
    parser.add_argument("--output", default="fda_denovo_export", help="Nom de fichier de sortie (sans extension)")
    parser.add_argument("--db", default=None, help="Chemin sqlite pour écrire aussi les records (optionnel)")
    args = parser.parse_args()

    search = build_search_query(args)
    records = client.fetch_all(BASE_URL, search, args.limit, args.api_key, extract_record)

    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    csv_fields = FIELDS_OF_INTEREST + ["advisory_committee", "clearance_type"]
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