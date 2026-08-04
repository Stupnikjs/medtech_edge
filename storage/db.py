"""
db.py - Persistance SQLite pour l'outil de scoring MedTech
=============================================================

Miroir des entités de models.py (RawClearanceRecord, Company, Device,
DeviceScore, ClearanceEvent, TickerScore), mais en tables SQLite plutot
qu'en objets Python.

Ce module fait 2 choses, et rien de plus :
  1. Stocker les records bruts issus des 3 parsers (510k / pma / denovo),
     avec dedup automatique -> c'est le besoin immediat.
  2. Fournir un schema + des fonctions CRUD basiques pour companies /
     devices / scores / events / ticker_scores, prêtes a être utilisées
     quand la logique de résolution (applicant_raw -> Company, matching
     de devices) existera. Cette logique de matching N'EST PAS ici -
     c'est un algo a part, pas de la persistance, et le deviner
     maintenant serait de la sur-ingenierie.

Pas d'ORM, pas de pool de connexions : c'est un script d'ingestion batch
qui tourne seul (un run de parser a la fois), pas un bot concurrent.
Un sqlite3.Connection + PRAGMA WAL suffit largement.
"""

import json
import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS raw_clearance_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT    NOT NULL,   -- openFDA_510k / openFDA_pma / openFDA_denovo
    record_number   TEXT    NOT NULL,   -- k_number / pma_number / denovo_number
    device_name     TEXT,
    applicant_raw   TEXT,
    decision_date   TEXT,               -- ISO yyyy-mm-dd
    decision_code   TEXT,
    clearance_type  TEXT,
    product_code    TEXT,
    advisory_committee TEXT,
    extra_json      TEXT,               -- champs additionnels specifiques a l'endpoint
    ingested_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source, record_number)
);

CREATE INDEX IF NOT EXISTS idx_raw_product_code ON raw_clearance_records(product_code);
CREATE INDEX IF NOT EXISTS idx_raw_applicant ON raw_clearance_records(applicant_raw);
CREATE INDEX IF NOT EXISTS idx_raw_decision_date ON raw_clearance_records(decision_date);

CREATE TABLE IF NOT EXISTS companies (
    company_id      TEXT PRIMARY KEY,
    canonical_name  TEXT NOT NULL,
    ticker          TEXT,
    exchange        TEXT,
    market_cap_tier TEXT NOT NULL DEFAULT 'private'
);

CREATE TABLE IF NOT EXISTS company_aliases (
    company_id  TEXT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    alias       TEXT NOT NULL,
    UNIQUE (company_id, alias)
);

CREATE TABLE IF NOT EXISTS devices (
    device_id           TEXT PRIMARY KEY,
    canonical_name      TEXT NOT NULL,
    normalized_name     TEXT NOT NULL,
    product_code        TEXT,
    device_class        TEXT,           -- I / II / III
    advisory_committee  TEXT,
    company_id          TEXT REFERENCES companies(company_id) ON DELETE SET NULL,
    status              TEXT NOT NULL DEFAULT 'active'
);

-- lien device <-> record brut (equivalent de Device.clearance_history)
CREATE TABLE IF NOT EXISTS device_clearance_links (
    device_id       TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    raw_record_id   INTEGER NOT NULL REFERENCES raw_clearance_records(id) ON DELETE CASCADE,
    UNIQUE (device_id, raw_record_id)
);

CREATE TABLE IF NOT EXISTS device_scores (
    score_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    score_version       TEXT NOT NULL DEFAULT 'v1.0',
    components_json     TEXT NOT NULL,   -- dict components tel que DeviceScore.components
    confidence          REAL NOT NULL DEFAULT 1.0,
    composite_score     REAL NOT NULL,
    computed_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_device_scores_device ON device_scores(device_id);

CREATE TABLE IF NOT EXISTS clearance_events (
    event_id                TEXT PRIMARY KEY,
    device_id               TEXT REFERENCES devices(device_id) ON DELETE CASCADE,
    company_id               TEXT REFERENCES companies(company_id) ON DELETE CASCADE,
    event_type               TEXT NOT NULL,   -- 510k_cleared / pma_approved / denovo_granted / recall_issued
    event_date                TEXT NOT NULL,
    headline                  TEXT,
    score_delta               REAL NOT NULL DEFAULT 0.0,
    source_raw_record_id      INTEGER REFERENCES raw_clearance_records(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_events_company ON clearance_events(company_id);

-- equivalent de TickerScore.contributing_devices
CREATE TABLE IF NOT EXISTS ticker_score_contributions (
    company_id      TEXT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    device_id       TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    weight          REAL NOT NULL,
    score_id        INTEGER NOT NULL REFERENCES device_scores(score_id) ON DELETE CASCADE,
    computed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, device_id, score_id)
);

-- equivalent de TickerScore.score_trend
CREATE TABLE IF NOT EXISTS ticker_score_trend (
    company_id       TEXT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    as_of            TEXT NOT NULL,
    composite_score  REAL NOT NULL,
    UNIQUE (company_id, as_of)
);
"""


def init_db(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Records bruts (le besoin immediat : sortie des 3 parsers -> sqlite)
# ---------------------------------------------------------------------------

# Colonnes "connues" qu'on range dans des colonnes dédiées ; tout le reste
# d'un record va dans extra_json. record_number_field permet a chaque parser
# de dire quel champ source sert d'identifiant (k_number / pma_number / denovo_number).
_KNOWN_COLUMNS = {
    "device_name", "applicant_raw", "decision_date", "decision_code",
    "clearance_type", "product_code", "advisory_committee",
}


def insert_raw_records(conn: sqlite3.Connection, records: list[dict], source: str,
                        record_number_field: str) -> int:
    """Insere une liste de records normalises (sortie des parsers).

    Chaque `record` doit contenir au moins `record_number_field` (l'identifiant
    FDA) ; les autres champs connus sont ranges dans des colonnes dédiées,
    le reste part dans extra_json. Dedup automatique sur (source, record_number)
    via ON CONFLICT DO UPDATE (idempotent : relancer le parser met juste a jour).
    """
    rows = []
    for r in records:
        record_number = r.get(record_number_field)
        if not record_number:
            continue  # pas d'identifiant -> on ne peut pas dedupliquer, on skip
        extra = {k: v for k, v in r.items() if k not in _KNOWN_COLUMNS and k != record_number_field}
        rows.append((
            source,
            record_number,
            r.get("device_name"),
            r.get("applicant_raw") or r.get("applicant"),
            r.get("decision_date"),
            r.get("decision_code"),
            r.get("clearance_type"),
            r.get("product_code"),
            r.get("advisory_committee"),
            json.dumps(extra, ensure_ascii=False),
        ))

    conn.executemany(
        """
        INSERT INTO raw_clearance_records
            (source, record_number, device_name, applicant_raw, decision_date,
             decision_code, clearance_type, product_code, advisory_committee, extra_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (source, record_number) DO UPDATE SET
            device_name = excluded.device_name,
            applicant_raw = excluded.applicant_raw,
            decision_date = excluded.decision_date,
            decision_code = excluded.decision_code,
            clearance_type = excluded.clearance_type,
            product_code = excluded.product_code,
            advisory_committee = excluded.advisory_committee,
            extra_json = excluded.extra_json
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def get_raw_records(conn: sqlite3.Connection, source: str | None = None) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if source:
        cur.execute("SELECT * FROM raw_clearance_records WHERE source = ? ORDER BY decision_date", (source,))
    else:
        cur.execute("SELECT * FROM raw_clearance_records ORDER BY decision_date")
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Companies / Devices / Scores / Events / TickerScore
# Fonctions basiques, appelees une fois la resolution (raw -> entite) faite
# ailleurs. Acceptent soit un objet models.py, soit un dict equivalent.
# ---------------------------------------------------------------------------

def _attr(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def upsert_company(conn: sqlite3.Connection, company) -> None:
    conn.execute(
        """
        INSERT INTO companies (company_id, canonical_name, ticker, exchange, market_cap_tier)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (company_id) DO UPDATE SET
            canonical_name = excluded.canonical_name,
            ticker = excluded.ticker,
            exchange = excluded.exchange,
            market_cap_tier = excluded.market_cap_tier
        """,
        (
            _attr(company, "company_id"),
            _attr(company, "canonical_name"),
            _attr(company, "ticker"),
            _attr(company, "exchange"),
            _attr(company, "market_cap_tier", "private"),
        ),
    )
    for alias in _attr(company, "known_aliases", []) or []:
        conn.execute(
            "INSERT OR IGNORE INTO company_aliases (company_id, alias) VALUES (?, ?)",
            (_attr(company, "company_id"), alias),
        )
    # conn.commit()


def upsert_device(conn: sqlite3.Connection, device) -> None:
    conn.execute(
        """
        INSERT INTO devices (device_id, canonical_name, normalized_name, product_code, device_class,
                              advisory_committee, company_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (device_id) DO UPDATE SET
            canonical_name = excluded.canonical_name,
            normalized_name = excluded.normalized_name,
            product_code = excluded.product_code,
            device_class = excluded.device_class,
            advisory_committee = excluded.advisory_committee,
            company_id = excluded.company_id,
            status = excluded.status
        """,
        (
            _attr(device, "device_id"),
            _attr(device, "canonical_name"),
            _attr(device, "normalized_name"),
            _attr(device, "product_code"),
            _attr(device, "device_class"),
            _attr(device, "advisory_committee"),
            _attr(device, "company_id"),
            _attr(device, "status", "active"),
        ),
    )
    conn.commit()


def link_device_clearance(conn: sqlite3.Connection, device_id: str, raw_record_id: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO device_clearance_links (device_id, raw_record_id) VALUES (?, ?)",
        (device_id, raw_record_id),
    )
    conn.commit()


def insert_device_score(conn: sqlite3.Connection, device_score) -> int:
    cur = conn.execute(
        """
        INSERT INTO device_scores (device_id, score_version, components_json, confidence, composite_score)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            _attr(device_score, "device_id"),
            _attr(device_score, "score_version", "v1.0"),
            json.dumps(_attr(device_score, "components", {}), ensure_ascii=False),
            _attr(device_score, "confidence", 1.0),
            _attr(device_score, "composite_score"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def insert_clearance_event(conn: sqlite3.Connection, event, source_raw_record_id: int | None = None) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO clearance_events
            (event_id, device_id, company_id, event_type, event_date, headline,
             score_delta, source_raw_record_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _attr(event, "event_id"),
            _attr(event, "device_id"),
            _attr(event, "company_id"),
            _attr(event, "event_type"),
            _attr(event, "event_date"),
            _attr(event, "headline"),
            _attr(event, "score_delta", 0.0),
            source_raw_record_id,
        ),
    )
    conn.commit()


def add_ticker_contribution(conn: sqlite3.Connection, company_id: str, device_id: str,
                             weight: float, score_id: int) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO ticker_score_contributions (company_id, device_id, weight, score_id)
        VALUES (?, ?, ?, ?)
        """,
        (company_id, device_id, weight, score_id),
    )
    conn.commit()


def add_ticker_trend_point(conn: sqlite3.Connection, company_id: str, as_of: str,
                            composite_score: float) -> None:
    conn.execute(
        """
        INSERT INTO ticker_score_trend (company_id, as_of, composite_score)
        VALUES (?, ?, ?)
        ON CONFLICT (company_id, as_of) DO UPDATE SET composite_score = excluded.composite_score
        """,
        (company_id, as_of, composite_score),
    )
    conn.commit()