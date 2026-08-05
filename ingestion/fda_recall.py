"""
Ingestion openFDA - Device Recalls (Enforcement Reports)
=========================================================

Source : https://api.fda.gov/device/enforcement.json
Doc    : https://open.fda.gov/apis/device/enforcement/

C'est l'endpoint "recalls" mentionné dans roadmap.md (device/enforcement,
pas device/recall qui est un endpoint different et moins utilise). Chaque
ligne = une action de recall/correction de marché, avec sa classification
de gravité (Class I = risque le plus grave, III = le moins grave).

Schema pas verifie par un curl live pendant l'ecriture de ce fichier
(contrairement au pma que Claude a confirme le 2026-08-02) - les noms de
champs ci-dessous viennent de la doc openFDA publique standard pour cet
endpoint, stable depuis longtemps. A verifier quand meme avant un run en
prod avec :
    curl "https://api.fda.gov/device/enforcement.json?limit=1"
device_name/device_class sont niches sous `openfda.*` comme pour le pma.

Usage :
    python fda_recall.py --start-date 2024-01-01 --end-date 2026-08-01
    python fda_recall.py --recalling-firm "Medtronic" --db ../medtech.db
    python fda_recall.py --product-code QKQ --classification "Class I"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion import open_fda as client
from storage import db

BASE_URL = "https://api.fda.gov/device/enforcement.json"
SOURCE = "openFDA_recall"
RECORD_NUMBER_FIELD = "recall_number"
DATE_FIELD = "recall_initiation_date"

FIELDS_OF_INTEREST = [
    "recall_number",
    "event_id",
    "status",
    "classification",          # "Class I" / "Class II" / "Class III"
    "product_description",
    "code_info",
    "product_quantity",
    "reason_for_recall",
    "recalling_firm",
    "city",
    "state",
    "country",
    "voluntary_mandated",
    "initial_firm_notification",
    "distribution_pattern",
    "product_code",
    "event_date_initiated",
    "event_date_created",
    "event_date_terminated",
    "event_date_posted",
    "report_date",
    "decision_code", 
    "applicant", 
    "decision_date"
]


def extract_record(raw: dict) -> dict:
    record = {field: raw.get(field, "") for field in FIELDS_OF_INTEREST}
    # device_name/device_class niches sous openfda, comme pour le pma
    openfda = raw.get("openfda", {}) or {}
    record["device_name"] = (openfda.get("device_name") or record.get("product_description", ""))
    record["device_class"] = openfda.get("device_class", "")
    # normalisation pour coller au schema commun (raw_clearance_records)
    record["applicant"] = record.get("recalling_firm", "")
    record["decision_date"] = record.get(DATE_FIELD, "")
    record["decision_code"] = record.get("classification", "")
    record["clearance_type"] = "Recall"
    return record


def build_search_query(args: argparse.Namespace) -> str | None:
    clauses = []
    if args.recalling_firm:
        clauses.append(f'recalling_firm:"{args.recalling_firm}"')
    if args.product_code:
        clauses.append(f'product_code:"{args.product_code}"')
    if args.classification:
        clauses.append(f'classification:"{args.classification}"')
    if args.status:
        clauses.append(f'status:"{args.status}"')

    date_clause = client.build_date_clause(args.start_date, args.end_date, field=DATE_FIELD)
    if date_clause:
        clauses.append(date_clause)

    return "+AND+".join(clauses) if clauses else None


def main():
    parser = argparse.ArgumentParser(description="Ingestion openFDA Device Recalls (enforcement)")
    parser.add_argument("--start-date", help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--recalling-firm", help="Nom de l'entreprise qui rappelle le device")
    parser.add_argument("--product-code", help="Code produit FDA (ex: QKQ)")
    parser.add_argument("--classification", help='Gravite ("Class I", "Class II", "Class III")')
    parser.add_argument("--status", help='Statut du recall (ex: "Ongoing", "Terminated")')
    parser.add_argument("--limit", type=int, default=1000, help="Nombre max d'enregistrements (0 = tout, prudence)")
    parser.add_argument("--api-key", default=None, help="Clé API openFDA (optionnelle)")
    parser.add_argument("--output", default="fda_recall_export", help="Nom de fichier de sortie (sans extension)")
    parser.add_argument("--db", default=None, help="Chemin sqlite pour écrire aussi les records (optionnel)")
    args = parser.parse_args()

    search = build_search_query(args)
    records = client.fetch_all(BASE_URL, search, args.limit, args.api_key, extract_record)

    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    """
    raise ValueError("dict contains fields not in fieldnames: "
    ValueError: dict contains fields not in fieldnames: 'decision_code', 'applicant', 'decision_date'
    """
    csv_fields = FIELDS_OF_INTEREST + ["device_name", "device_class", "clearance_type"]
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