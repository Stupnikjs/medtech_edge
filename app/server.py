# api.py

import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

DB_PATH = Path("medtech.db")

app = FastAPI(
    title="MedTech Scoring API",
    version="1.0.0",
    description="API de consultation des companies et devices."
)

# Autorise les appels depuis un frontend (React/Vue/etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dict(rows):
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "name": "MedTech Scoring API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------

@app.get("/companies")
def get_companies():
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM companies
        ORDER BY canonical_name
        """
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


@app.get("/companies/{company_id}")
def get_company(company_id: str):
    conn = get_conn()

    row = conn.execute(
        """
        SELECT *
        FROM companies
        WHERE company_id = ?
        """,
        (company_id,),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Company not found")

    return dict(row)


@app.get("/companies/{company_id}/devices")
def get_company_devices(company_id: str):
    conn = get_conn()

    company = conn.execute(
        """
        SELECT *
        FROM companies
        WHERE company_id = ?
        """,
        (company_id,),
    ).fetchone()

    if company is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Company not found")

    devices = conn.execute(
        """
        SELECT *
        FROM devices
        WHERE company_id = ?
        ORDER BY canonical_name
        """,
        (company_id,),
    ).fetchall()

    conn.close()

    return {
        "company": dict(company),
        "devices": rows_to_dict(devices),
    }


# ---------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------

@app.get("/devices")
def get_devices():
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM devices
        ORDER BY canonical_name
        """
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


@app.get("/devices/{device_id}")
def get_device(device_id: str):
    conn = get_conn()

    row = conn.execute(
        """
        SELECT *
        FROM devices
        WHERE device_id = ?
        """,
        (device_id,),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return dict(row)


@app.get("/devices/{device_id}/details")
def get_device_details(device_id: str):
    conn = get_conn()

    row = conn.execute(
        """
        SELECT
            d.*,
            c.company_id,
            c.canonical_name AS company_name,
            c.ticker,
            c.exchange,
            c.market_cap_tier
        FROM devices d
        LEFT JOIN companies c
            ON d.company_id = c.company_id
        WHERE d.device_id = ?
        """,
        (device_id,),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return dict(row)


# ---------------------------------------------------------------------
# Raw FDA Records
# ---------------------------------------------------------------------

@app.get("/raw-records")
def get_raw_records():
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM raw_clearance_records
        ORDER BY decision_date DESC
        """
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


@app.get("/raw-records/{record_id}")
def get_raw_record(record_id: int):
    conn = get_conn()

    row = conn.execute(
        """
        SELECT *
        FROM raw_clearance_records
        WHERE id = ?
        """,
        (record_id,),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Record not found")

    return dict(row)


# ---------------------------------------------------------------------
# Device Scores
# ---------------------------------------------------------------------

@app.get("/device-scores")
def get_device_scores():
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM device_scores
        ORDER BY computed_at DESC
        """
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


@app.get("/device-scores/{device_id}")
def get_scores_for_device(device_id: str):
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM device_scores
        WHERE device_id = ?
        ORDER BY computed_at DESC
        """,
        (device_id,),
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


# ---------------------------------------------------------------------
# Clearance Events
# ---------------------------------------------------------------------

@app.get("/events")
def get_events():
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM clearance_events
        ORDER BY event_date DESC
        """
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


@app.get("/events/company/{company_id}")
def get_company_events(company_id: str):
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM clearance_events
        WHERE company_id = ?
        ORDER BY event_date DESC
        """,
        (company_id,),
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


@app.get("/events/device/{device_id}")
def get_device_events(device_id: str):
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM clearance_events
        WHERE device_id = ?
        ORDER BY event_date DESC
        """,
        (device_id,),
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


# ---------------------------------------------------------------------
# Ticker Score Trend
# ---------------------------------------------------------------------

@app.get("/ticker-trend/{company_id}")
def get_ticker_trend(company_id: str):
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM ticker_score_trend
        WHERE company_id = ?
        ORDER BY as_of DESC
        """,
        (company_id,),
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


# ---------------------------------------------------------------------
# Contributions
# ---------------------------------------------------------------------

@app.get("/ticker-contributions/{company_id}")
def get_contributions(company_id: str):
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT
            t.company_id,
            t.device_id,
            d.canonical_name AS device_name,
            t.weight,
            t.score_id,
            t.computed_at
        FROM ticker_score_contributions t
        LEFT JOIN devices d
            ON t.device_id = d.device_id
        WHERE t.company_id = ?
        ORDER BY t.weight DESC
        """,
        (company_id,),
    ).fetchall()

    conn.close()

    return rows_to_dict(rows)


# ---------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------

@app.get("/stats")
def stats():
    conn = get_conn()

    stats = {
        "companies": conn.execute(
            "SELECT COUNT(*) FROM companies"
        ).fetchone()[0],
        "devices": conn.execute(
            "SELECT COUNT(*) FROM devices"
        ).fetchone()[0],
        "raw_records": conn.execute(
            "SELECT COUNT(*) FROM raw_clearance_records"
        ).fetchone()[0],
        "events": conn.execute(
            "SELECT COUNT(*) FROM clearance_events"
        ).fetchone()[0],
        "device_scores": conn.execute(
            "SELECT COUNT(*) FROM device_scores"
        ).fetchone()[0],
    }

    conn.close()

    return stats


# ---------------------------------------------------------------------
# Lancement :
#
# uvicorn api:app --reload
#
# Documentation :
# http://127.0.0.1:8000/docs
# ---------------------------------------------------------------------