"""
fill_companies.py - Normalise applicant_raw -> Company, avec ticker SEC si dispo.

Améliorations vs version initiale :
- normalize_name gère accents, "&", préfixe "THE", ponctuation étendue
- fuzzy-match aussi contre les companies déjà en base (pas seulement SEC)
- blocking (première lettre) avant fuzzy match pour limiter le coût du scan
- alias enregistré même en cas de match exact, pour enrichir company_aliases
"""

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import requests
from rapidfuzz import fuzz, process

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.db import get_raw_records, upsert_company, upsert_alias, init_db
from models import Company  # adapte le chemin

SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_CACHE = Path("data/sec_company_tickers.json")
HEADERS = {"User-Agent": "medtech_edge research contact@example.com"}  # mets ton vrai contact

# Suffixes juridiques à retirer (US + international, medtech ayant beaucoup de fabricants hors US)
CORP_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|plc|"
    r"sa|nv|bv|spa|srl|sarl|kk|pty|pvt|oyj|ab|as|kg|bhd|sdn bhd|"
    r"ag|gmbh|holdings?|group)\b\.?",
    re.IGNORECASE,
)

# Abréviations métier fréquentes dans les raisons sociales FDA -> forme longue,
# pour que "XXX MFG" et "XXX MANUFACTURING" se normalisent pareil.
BUSINESS_ABBR = {
    r"\bMFG\b": "MANUFACTURING",
    r"\bINTL\b": "INTERNATIONAL",
    r"\bLABS\b": "LABORATORIES",
}


def normalize_name(raw: str) -> str:
    """Normalise un nom brut pour comparaison : accents retirés, majuscules,
    ponctuation nettoyée, suffixes juridiques et préfixe 'THE' supprimés,
    abréviations métier dépliées, espaces compactés."""
    # retire les accents (Société -> Societe)
    name = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
    name = name.upper()
    name = name.replace("&", " AND ")
    name = re.sub(r"[.,'/()\-]", " ", name)

    for pattern, repl in BUSINESS_ABBR.items():
        name = re.sub(pattern, repl, name)

    name = CORP_SUFFIXES.sub("", name)
    name = re.sub(r"^\s*THE\s+", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# SEC ticker source (cache local, refresh manuel)
# ---------------------------------------------------------------------------

def load_sec_tickers() -> dict[str, tuple[str, str]]:
    """Charge (ou télécharge et met en cache) le mapping SEC nom_normalise -> (ticker, exchange)."""
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


def build_blocking_index(names) -> dict[str, list[str]]:
    """Regroupe des noms normalisés par première lettre, pour réduire le nombre
    de candidats passés au fuzzy matcher (évite de scanner tout le mapping SEC
    ou toute la table companies à chaque record)."""
    index = defaultdict(list)
    for name in names:
        if name:
            index[name[0]].append(name)
    return index


def fuzzy_lookup(normalized_name: str, blocking_index: dict, mapping: dict, threshold: int):
    """Cherche le meilleur candidat fuzzy dans le même bloc (même première lettre)
    que normalized_name. Retourne la clé matchée dans `mapping`, ou None."""
    if not normalized_name:
        return None
    candidates = blocking_index.get(normalized_name[0], [])
    if not candidates:
        return None
    result = process.extractOne(normalized_name, candidates, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= threshold:
        return result[0]
    return None


def match_ticker(normalized_name: str, sec_mapping: dict, sec_blocking: dict, threshold: int):
    """Trouve un ticker SEC pour un nom normalisé : match exact d'abord, puis fuzzy
    (limité au bloc de même première lettre)."""
    if normalized_name in sec_mapping:
        return sec_mapping[normalized_name]

    matched_name = fuzzy_lookup(normalized_name, sec_blocking, sec_mapping, threshold)
    if matched_name:
        return sec_mapping[matched_name]
    return None, None


# ---------------------------------------------------------------------------
# Résolution
# ---------------------------------------------------------------------------

def load_existing_companies(conn: sqlite3.Connection) -> dict[str, str]:
    """{nom_normalise: company_id}, en couvrant canonical_name ET aliases déjà connus."""
    mapping = {}
    for row in conn.execute("SELECT company_id, canonical_name FROM companies"):
        mapping[normalize_name(row["canonical_name"])] = row["company_id"]
    for row in conn.execute("SELECT company_id, alias FROM company_aliases"):
        mapping[normalize_name(row["alias"])] = row["company_id"]
    return mapping


def resolve_existing_company(norm: str, existing: dict, existing_blocking: dict, threshold: int):
    """Tente de rattacher norm à une company déjà en base : match exact, puis fuzzy
    contre les companies existantes (et pas seulement contre SEC). C'est ce qui évite
    de créer un doublon pour une simple variante orthographique."""
    if norm in existing:
        return existing[norm], "exact"

    matched_name = fuzzy_lookup(norm, existing_blocking, existing, threshold)
    if matched_name:
        return existing[matched_name], "fuzzy"
    return None, None


def main():
    parser = argparse.ArgumentParser(description="Resolve companies from raw_clearance_records")
    parser.add_argument("--db", required=True)
    parser.add_argument("--ticker-threshold", type=int, default=90)
    parser.add_argument("--dedup-threshold", type=int, default=92)  # seuil un peu plus strict pour éviter de fusionner 2 vraies boîtes différentes
    args = parser.parse_args()

    conn = init_db(args.db)
    conn.row_factory = sqlite3.Row

    sec_mapping = load_sec_tickers()
    sec_blocking = build_blocking_index(sec_mapping.keys())

    existing = load_existing_companies(conn)
    existing_blocking = build_blocking_index(existing.keys())

    records = get_raw_records(conn=conn)

    created = 0
    reused_exact = 0
    reused_fuzzy = 0
    ticker_found = 0
    skipped = 0

    for raw in records:
        applicant_raw = raw["applicant_raw"]
        if not applicant_raw:
            skipped += 1
            continue

        norm = normalize_name(applicant_raw)

        company_id, match_type = resolve_existing_company(norm, existing, existing_blocking, args.dedup_threshold)

        if company_id:
            # même en cas de réutilisation, on garde la variante brute comme alias
            # pour enrichir les futurs matchs exacts (et éviter de refuzzy-matcher pour rien)
            upsert_alias(conn, company_id, applicant_raw.strip())
            if match_type == "exact":
                reused_exact += 1
            else:
                reused_fuzzy += 1
        else:
            ticker, exchange = match_ticker(norm, sec_mapping, sec_blocking, args.ticker_threshold)

            company = Company(
                canonical_name=applicant_raw.strip(),
                ticker=ticker,
                exchange=exchange,
                market_cap_tier="public" if ticker else "private",
            )
            if hasattr(company, "known_aliases"):
                company.known_aliases = [applicant_raw.strip()]

            upsert_company(conn, company)
            company_id = company.company_id

            # met à jour les index en mémoire pour que les records suivants
            # puissent matcher cette nouvelle company sans relire la DB
            existing[norm] = company_id
            existing_blocking[norm[0]].append(norm) if norm else None

            created += 1
            if ticker:
                ticker_found += 1

        # ici : UPDATE devices SET company_id=? WHERE device_id IN (...)
        # selon comment tu relies raw -> device dans ton pipeline

    print(
        f"{created} companies créées ({ticker_found} avec ticker) / "
        f"{reused_exact} réutilisées (exact) / {reused_fuzzy} réutilisées (fuzzy) / {skipped} skip"
    )


if __name__ == "__main__":
    main()
