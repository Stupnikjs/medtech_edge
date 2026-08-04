"""
resolve_companies.py - Normalise applicant_raw -> Company, avec ticker SEC si dispo.
"""

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

import requests
from rapidfuzz import fuzz, process


from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from storage.db import get_raw_records, upsert_company, init_db
from models import Company  # adapte le chemin

SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_CACHE = Path("data/sec_company_tickers.json")
HEADERS = {"User-Agent": "medtech_edge research contact@example.com"}  # mets ton vrai contact

CORP_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|plc|sa|ag|gmbh|holdings?|group)\b\.?",
    re.IGNORECASE,
)


def normalize_name(raw: str) -> str:
    name = raw.upper()
    name = re.sub(r"[.,]", "", name)
    name = CORP_SUFFIXES.sub("", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# SEC ticker source (cache local, refresh manuel)
# ---------------------------------------------------------------------------

def load_sec_tickers() -> dict[str, tuple[str, str]]:
    """Retourne {nom_normalise: (ticker, exchange)}."""
    if SEC_CACHE.exists():
        raw = json.loads(SEC_CACHE.read_text())
    else:
        resp = requests.get(SEC_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
        SEC_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SEC_CACHE.write_text(json.dumps(raw))

    fields = raw["fields"]  # ["cik", "name", "ticker", "exchange"]
    idx = {f: i for i, f in enumerate(fields)}

    mapping = {}
    for row in raw["data"]:
        name = row[idx["name"]]
        ticker = row[idx["ticker"]]
        exchange = row[idx["exchange"]]
        mapping[normalize_name(name)] = (ticker, exchange)
    return mapping


def match_ticker(normalized_name: str, sec_mapping: dict, threshold: int = 90):
    if normalized_name in sec_mapping:
        return sec_mapping[normalized_name]  # match exact, pas besoin de fuzzy

    result = process.extractOne(
        normalized_name, sec_mapping.keys(), scorer=fuzz.token_sort_ratio
    )
    if result and result[1] >= threshold:
        matched_name = result[0]
        return sec_mapping[matched_name]
    return None, None


# ---------------------------------------------------------------------------
# Résolution
# ---------------------------------------------------------------------------

def load_existing_companies(conn: sqlite3.Connection) -> dict[str, str]:
    """{nom_normalise: company_id}, en couvrant canonical_name ET aliases."""
    mapping = {}
    for row in conn.execute("SELECT company_id, canonical_name FROM companies"):
        mapping[normalize_name(row["canonical_name"])] = row["company_id"]
    for row in conn.execute("SELECT company_id, alias FROM company_aliases"):
        mapping[normalize_name(row["alias"])] = row["company_id"]
    return mapping


def main():
    parser = argparse.ArgumentParser(description="Resolve companies from raw_clearance_records")
    parser.add_argument("--db", required=True)
    parser.add_argument("--ticker-threshold", type=int, default=90)
    args = parser.parse_args()

    conn = init_db(args.db)
    conn.row_factory = sqlite3.Row

    sec_mapping = load_sec_tickers()
    existing = load_existing_companies(conn)

    records = get_raw_records(conn=conn)

    created = 0
    reused = 0
    ticker_found = 0
    skipped = 0

    for raw in records:
        applicant_raw = raw["applicant_raw"]
        if not applicant_raw:
            skipped += 1
            continue

        norm = normalize_name(applicant_raw)

        if norm in existing:
            company_id = existing[norm]
            reused += 1
        else:
            ticker, exchange = match_ticker(norm, sec_mapping, args.ticker_threshold)

            company = Company(
                canonical_name=applicant_raw.strip(),
                ticker=ticker,
                exchange=exchange,
                market_cap_tier="public" if ticker else "private",
            )
            # si ta classe Company a known_aliases, ajoute le nom brut original
            if hasattr(company, "known_aliases"):
                company.known_aliases = [applicant_raw.strip()]

            upsert_company(conn, company)
            company_id = company.company_id
            existing[norm] = company_id
            created += 1
            if ticker:
                ticker_found += 1

        # ici tu peux ensuite faire un update device.company_id = company_id
        # via une requête UPDATE devices SET company_id=? WHERE device_id IN (...)
        # selon comment tu relies raw -> device dans ton pipeline

    print(f"{created} companies créées ({ticker_found} avec ticker) / {reused} réutilisées / {skipped} skip")


if __name__ == "__main__":
    main()