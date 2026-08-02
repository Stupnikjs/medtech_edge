"""
Parser openFDA - Device 510(k) Clearances
===========================================

Source : https://api.fda.gov/device/510k.json
Doc    : https://open.fda.gov/apis/device/510k/

Récupère les décisions de clearance 510(k) de la FDA (dispositifs médicaux)
et les exporte en CSV / JSON pour analyse ultérieure (scoring, matching
avec des tickers boursiers, suivi de pipeline par entreprise, etc.)

Aucune authentification requise pour un usage basique (40 req/min).
Une clé API gratuite (https://open.fda.gov/apis/authentication/) porte
la limite à 240 req/min — recommandé si tu comptes tout aspirer.

Usage :
    python fda_510k_parser.py --start-date 2024-01-01 --end-date 2026-08-01
    python fda_510k_parser.py --applicant "Medtronic"
    python fda_510k_parser.py --product-code QKQ --limit 500
"""

import argparse
import csv
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE_URL = "https://api.fda.gov/device/510k.json"
PAGE_SIZE = 100          # max autorisé par l'API par requête
RATE_LIMIT_DELAY = 0.3   # secondes entre 2 appels (marge sous 40 req/min)

# Champs les plus utiles pour un outil d'évaluation investisseur
FIELDS_OF_INTEREST = [
    "k_number",           # identifiant unique du dossier 510(k)
    "device_name",
    "applicant",          # nom de l'entreprise soumissionnaire
    "decision_date",
    "decision_description",
    "decision_code",
    "clearance_type",
    "product_code",
    "advisory_committee",       # spécialité clinique (cv, ho, ne, etc.)
    "advisory_committee_description",
    "third_party_flag",
    "statement_or_summary",
    "type",
    "review_advisory_committee",
    "expedited_review_flag",
]


def build_query(search: str | None, limit: int, skip: int, api_key: str | None) -> str:
    params = {"limit": limit, "skip": skip}
    if search:
        params["search"] = search
    if api_key:
        params["api_key"] = api_key
    return f"{BASE_URL}?{urlencode(params)}"


def fetch_page(search: str | None, limit: int, skip: int, api_key: str | None) -> dict:
    url = build_query(search, limit, skip, api_key)
    req = Request(url, headers={"User-Agent": "medtech-research-parser/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            # openFDA renvoie 404 quand la recherche ne matche plus rien
            # (fin de pagination) -> traiter comme résultat vide
            return {"results": []}
        raise
    except URLError as e:
        raise RuntimeError(f"Impossible de joindre l'API openFDA : {e}") from e


def extract_record(raw: dict) -> dict:
    """Ne garde que les champs utiles, en gérant les valeurs manquantes."""
    record = {}
    for field in FIELDS_OF_INTEREST:
        record[field] = raw.get(field, "")
    return record


def build_search_query(args: argparse.Namespace) -> str | None:
    """Construit la clause `search=` openFDA à partir des filtres CLI."""
    clauses = []

    if args.applicant:
        clauses.append(f'applicant:"{args.applicant}"')

    if args.product_code:
        clauses.append(f'product_code:"{args.product_code}"')

    if args.advisory_committee:
        clauses.append(f'advisory_committee:"{args.advisory_committee}"')

    if args.start_date and args.end_date:
        start = args.start_date.replace("-", "")
        end = args.end_date.replace("-", "")
        clauses.append(f"decision_date:[{start}+TO+{end}]")
    elif args.start_date:
        start = args.start_date.replace("-", "")
        clauses.append(f"decision_date:[{start}+TO+99991231]")
    elif args.end_date:
        end = args.end_date.replace("-", "")
        clauses.append(f"decision_date:[17760101+TO+{end}]")

    if not clauses:
        return None
    return "+AND+".join(clauses)


def fetch_all(args: argparse.Namespace) -> list[dict]:
    search = build_search_query(args)
    results: list[dict] = []
    skip = 0

    label = search or "(aucun filtre -- tout l'historique)"
    print(f"Requête openFDA : search={label}")

    while True:
        remaining = args.limit - len(results) if args.limit else PAGE_SIZE
        page_size = min(PAGE_SIZE, remaining) if args.limit else PAGE_SIZE
        if page_size <= 0:
            break

        data = fetch_page(search, page_size, skip, args.api_key)
        page_results = data.get("results", [])

        if not page_results:
            break

        results.extend(extract_record(r) for r in page_results)
        print(f"  -> {len(results)} enregistrements récupérés (skip={skip})")

        skip += page_size
        time.sleep(RATE_LIMIT_DELAY)

        # openFDA plafonne skip+limit à 26000 sur ce endpoint
        if skip >= 26000:
            print("  -> limite de pagination openFDA atteinte (skip max 26000).")
            print("     Pour aller plus loin : réduire la période avec --start-date/--end-date")
            break

        if args.limit and len(results) >= args.limit:
            break

    return results


def save_csv(records: list[dict], path: Path) -> None:
    if not records:
        print("Aucun enregistrement à sauvegarder.")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS_OF_INTEREST)
        writer.writeheader()
        writer.writerows(records)
    print(f"CSV écrit : {path} ({len(records)} lignes)")


def save_json(records: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"JSON écrit : {path} ({len(records)} enregistrements)")


def main():
    parser = argparse.ArgumentParser(description="Parser openFDA Device 510(k)")
    parser.add_argument("--start-date", help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--applicant", help="Nom de l'entreprise soumissionnaire")
    parser.add_argument("--product-code", help="Code produit FDA (ex: QKQ)")
    parser.add_argument("--advisory-committee", help="Code comité consultatif (ex: cv, ho, ne)")
    parser.add_argument("--limit", type=int, default=1000, help="Nombre max d'enregistrements (0 = tout, prudence)")
    parser.add_argument("--api-key", default=None, help="Clé API openFDA (optionnelle, augmente le rate limit)")
    parser.add_argument("--output", default="fda_510k_export", help="Nom de fichier de sortie (sans extension)")
    args = parser.parse_args()

    records = fetch_all(args)

    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)

    save_csv(records, out_dir / f"{args.output}.csv")
    save_json(records, out_dir / f"{args.output}.json")


if __name__ == "__main__":
    main()
