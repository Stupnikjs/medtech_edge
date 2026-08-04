"""
backfill.py - Backfill historique multi-annees, multi-parsers
===============================================================

Itere sur les 4 endpoints openFDA (510k, pma, denovo, recall) annee civile
par annee civile, sur une fenetre par defaut de 20 ans. Le decoupage par
annee n'est pas cosmetique : c'est pour rester sous la limite de pagination
openFDA (skip+limit <= 26000, voir MAX_SKIP dans open_fda.py) meme sur les
endpoints a fort volume (510k, recall) ou 20 ans d'un coup depasserait
largement ce plafond.

Volontairement un backfill BRUT : pas de --applicant / --product-code /
etc., juste la fenetre de dates propre a chaque endpoint (decision_date
pour 510k/pma/denovo, event_date_initiated pour recall via DATE_FIELD).
Pour un fetch filtre, on utilise directement le parser concerne.

Chaque annee/parser est isolee dans son propre try/except : si openFDA
renvoie une erreur sur une annee donnee (timeout, 5xx...), on log et on
continue plutot que de perdre tout le run.

Usage :
    python backfill.py --db ../medtech.db
    python backfill.py --db ../medtech.db --years 5 --only fda_510k,fda_recall
    python backfill.py --db ../medtech.db --start-year 2015 --end-year 2020
    python backfill.py --db ../medtech.db --api-key XXXX   # recommande sur 20 ans (rate limit sans cle : 40 req/min)
"""

import argparse
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion import open_fda as client
from ingestion import fda_510k, fda_pma, fda_denovo, fda_recall
from storage import db

PARSERS = [
    {"name": "fda_510k", "module": fda_510k},
    {"name": "fda_pma", "module": fda_pma},
    {"name": "fda_denovo", "module": fda_denovo},
    {"name": "fda_recall", "module": fda_recall},
]



T1 = type(str, str)
def year_ranges(start_year: int, end_year: int) -> T1: # type: ignore
    """Genere des tuples (start_date, end_date) annee civile par annee civile.
    La derniere annee est bornee a aujourd'hui si elle correspond a l'annee en cours."""
    today = date.today()
    for year in range(start_year, end_year + 1):
        start = f"{year}-01-01"
        end = today.isoformat() if year == today.year else f"{year}-12-31"
        yield start, end


def fetch_year(module, start_date: str, end_date: str, api_key: str | None) -> list[dict]:
    date_field = getattr(module, "DATE_FIELD", "decision_date")
    search = client.build_date_clause(start_date, end_date, field=date_field)
    return client.fetch_all(module.BASE_URL, search, 0, api_key, module.extract_record)


def main():
    parser = argparse.ArgumentParser(description="Backfill multi-annees openFDA (510k/pma/denovo/recall)")
    parser.add_argument("--db", required=True, help="Chemin sqlite (ex: ../medtech.db)")
    parser.add_argument("--years", type=int, default=20, help="Nombre d'annees en arriere depuis aujourd'hui (defaut 20)")
    parser.add_argument("--start-year", type=int, default=None, help="Annee de debut explicite (prioritaire sur --years)")
    parser.add_argument("--end-year", type=int, default=None, help="Annee de fin explicite (defaut : annee courante)")
    parser.add_argument("--only", default=None, help="Sous-ensemble de parsers, ex: fda_510k,fda_recall")
    parser.add_argument("--api-key", default=None, help="Cle API openFDA (fortement recommandee sur un backfill de 20 ans)")
    parser.add_argument("--sleep-between-years", type=float, default=1.0, help="Pause (s) entre 2 annees, en plus du rate-limit interne au client")
    args = parser.parse_args()

    end_year = args.end_year or date.today().year
    start_year = args.start_year or (end_year - args.years + 1)

    only = set(args.only.split(",")) if args.only else None
    active_parsers = [p for p in PARSERS if only is None or p["name"] in only]
    if not active_parsers:
        print(f"Aucun parser ne correspond a --only={args.only}")
        return

    conn = db.init_db(args.db)
    print(f"Backfill {start_year}-{end_year} sur {[p['name'] for p in active_parsers]} -> {args.db}")
    if not args.api_key:
        print("(pas de --api-key : rate limit openFDA a 40 req/min, un backfill 20 ans/4 parsers peut prendre un moment)")

    grand_total = 0
    for p in active_parsers:
        module = p["module"]
        source = module.SOURCE
        record_field = module.RECORD_NUMBER_FIELD
        parser_total = 0

        for start_date, end_date in year_ranges(start_year, end_year):
            print(f"\n[{p['name']}] {start_date} -> {end_date}")
            try:
                records = fetch_year(module, start_date, end_date, args.api_key)
            except Exception as e:
                print(f"  ERREUR {p['name']} {start_date}/{end_date} : {e!r} -- annee skippee, on continue")
                continue

            if not records:
                print("  0 enregistrement")
                time.sleep(args.sleep_between_years)
                continue

            normalized = [{**r, "applicant_raw": r.get("applicant", "")} for r in records]
            n = db.insert_raw_records(conn, normalized, source, record_field)
            parser_total += n
            print(f"  {n} records upsertes (source={source})")

            time.sleep(args.sleep_between_years)

        print(f"[{p['name']}] total : {parser_total} records")
        grand_total += parser_total

    conn.close()
    print(f"\nBackfill termine : {grand_total} records au total dans {args.db}")


if __name__ == "__main__":
    main()