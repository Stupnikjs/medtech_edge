"""
openfda_client.py
==================

Logique commune aux 3 endpoints openFDA qu'on parse (510k, pma, denovo) :
requête HTTP + pagination, clause de date, écriture CSV/JSON.

Ce qui reste SPECIFIQUE a chaque module d'ingestion (et n'est donc PAS ici) :
- l'URL de base et la liste des champs utiles (FIELDS_OF_INTEREST)
- la fonction extract_record (mapping brut -> champs gardés)
- la fonction build_search_query (les filtres CLI propres a l'endpoint)

Volontairement pas de classe / pas d'abstraction "BaseIngestion" : 3 scripts
fonction par fonction, qui importent ces quelques helpers. Plus simple à
lire et à modifier que de la hiérarchie objet pour 3 endpoints qui ne
bougeront plus beaucoup.
"""

import json
import time
import requests
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PAGE_SIZE = 100          # max autorisé par page par l'API openFDA
RATE_LIMIT_DELAY = 0.3   # secondes entre 2 appels (marge sous 40 req/min sans clé)
MAX_SKIP = 26000         # openFDA plafonne skip+limit a 26000 sur ces endpoints


def build_query_url(base_url: str, search: str | None, limit: int, skip: int,
                     api_key: str | None) -> str:
    params = {"limit": limit, "skip": skip}
    if search:
        params["search"] = search
    if api_key:
        params["api_key"] = api_key
    return f"{base_url}?{urlencode(params)}"


import requests

def fetch_page(base_url, search, limit, skip, api_key):
    url = build_query_url(base_url, search, limit, skip, api_key)
    print(url)

    r = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
    )

    print(r.status_code)

    if r.status_code == 404:
        print(f"  -> corps de la réponse 404 : {r.text[:300]}")
        return {"results": []}

    r.raise_for_status()
    return r.json()

def build_date_clause(start_date: str | None, end_date: str | None,
                       field: str = "decision_date") -> str | None:
    """Clause `field:[debut+TO+fin]` commune aux 3 endpoints (tous ont decision_date)."""
    if start_date and end_date:
        start = start_date.replace("-", "")
        end = end_date.replace("-", "")
        return f"{field}:[{start} TO {end}]"
    if start_date:
        start = start_date.replace("-", "")
        return f"{field}:[{start} TO 99991231]"
    if end_date:
        end = end_date.replace("-", "")
        return f"{field}:[17760101 TO {end}]"
    return None


def fetch_all(base_url: str, search: str | None, limit: int, api_key: str | None,
              extract_fn) -> list[dict]:
    """Boucle de pagination générique.

    `extract_fn` transforme un résultat brut openFDA en dict "propre"
    (champs gardés). C'est la seule partie qui varie par endpoint.
    """
    results: list[dict] = []
    skip = 0

    label = search or "(aucun filtre -- tout l'historique)"
    print(f"Requête openFDA [{base_url}] : search={label}")

    while True:
        remaining = limit - len(results) if limit else PAGE_SIZE
        page_size = min(PAGE_SIZE, remaining) if limit else PAGE_SIZE
        if page_size <= 0:
            break

        data = fetch_page(base_url, search, page_size, skip, api_key)
        page_results = data.get("results", [])

        if not page_results:
            break

        results.extend(extract_fn(r) for r in page_results)
        print(f"  -> {len(results)} enregistrements récupérés (skip={skip})")

        skip += page_size
        time.sleep(RATE_LIMIT_DELAY)

        if skip >= MAX_SKIP:
            print(f"  -> limite de pagination openFDA atteinte (skip max {MAX_SKIP}).")
            print("     Pour aller plus loin : réduire la période avec --start-date/--end-date")
            break

        if limit and len(results) >= limit:
            break

    return results

def year_of(record: dict, date_field: str) -> str:
    """Extrait l'année (YYYY) d'un record depuis date_field. Retourne
    'unknown' si la date est absente ou mal formée, pour ne jamais perdre
    un record silencieusement à cause d'un champ vide."""
    value = record.get(date_field) or record.get("decision_date") or ""
    return value[:4] if len(value) >= 4 and value[:4].isdigit() else "unknown"


def partition_by_year(records: list[dict], date_field: str) -> dict[str, list[dict]]:
    """Regroupe les records par année pour l'écriture en dossiers partitionnés."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        buckets[year_of(r, date_field)].append(r)
    return buckets



def write_partitioned(records: list[dict], out_root: Path, filename: str, date_field:str) -> dict[str, int]:
    """Écrit les records en output/<source>/<year>/filename.json, un dossier par année."""
    partitioned = partition_by_year(records, date_field)
    counts = {}
    for year, year_records in sorted(partitioned.items()):
        
        year_dir = out_root / year
        year_dir.mkdir(parents=True, exist_ok=True)
        save_json(year_records, year_dir / f"{filename}.json")
        counts[year] = len(year_records)
    return counts


def save_csv(records: list[dict], path: Path, fieldnames: list[str]) -> None:
    import csv

    if not records:
        print("Aucun enregistrement à sauvegarder.")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"CSV écrit : {path} ({len(records)} lignes)")


def save_json(records: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"JSON écrit : {path} ({len(records)} enregistrements)")