import argparse
import json
import sqlite3
import re
import unicodedata
import sys


from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


from storage.db import get_raw_records, upsert_device, link_device_clearance, init_db
from models.schemas import Device



def normalize_device_name(name: str) -> str:
    if not name:
        return ""

    name = unicodedata.normalize("NFKD", name)
    name = name.upper()

    # apostrophes, tirets...
    name = re.sub(r"[-_/]", " ", name)

    # suppression de la ponctuation
    name = re.sub(r"[^\w\s]", "", name)

    # espaces multiples
    name = re.sub(r"\s+", " ", name).strip()

    return name


def load_existing_devices(conn):
    rows = conn.execute(
        "SELECT device_id, canonical_name, product_code FROM devices"
    ).fetchall()

    return {
        (
            normalize_device_name(row["canonical_name"]),
            row["product_code"] or "",
        ): row["device_id"]
        for row in rows
    }

def main():
    parser = argparse.ArgumentParser(description="Fill devices from raw_clearance_records")
    parser.add_argument("--db", required=True, help="Chemin sqlite (ex: ../medtech.db)")
    args = parser.parse_args()

    conn = init_db(args.db)
    conn.row_factory = sqlite3.Row
    records = get_raw_records(conn=conn)

    existing = load_existing_devices(conn)
    created = 0
    reused = 0
    skipped = 0

    for raw in records:
        name = raw["device_name"]
        if not name:
            skipped += 1
            continue

        product_code = raw["product_code"]

        normalized_name = normalize_device_name(name)
        key = (normalized_name, product_code or "")

        if key in existing:
            device_id = existing[key]
            reused += 1
        else:
            extra = json.loads(raw["extra_json"] or "{}")
            device_class = extra.get("device_class") or extra.get("openfda", {}).get("device_class")

            device = Device(
                canonical_name=name,
                normalized_name=normalized_name,
                product_code=product_code,
                device_class=device_class,
                advisory_committee=raw["advisory_committee"],
                company_id=None,  # résolution applicant_raw -> company_id pas encore faite
            )
            upsert_device(conn, device)
            device_id = device.device_id
            existing[key] = device_id  # évite de recréer si un autre raw record matche dans la même boucle
            created += 1

        link_device_clearance(conn, device_id, raw["id"])

    print(f"{created} devices créés / {reused} réutilisés / {len(records)} raw records traités / {skipped} skip")


if __name__ == "__main__":
    main()