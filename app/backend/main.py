"""Main FastAPI application for Argus Custode."""

import os
import sqlite3
from typing import Any, Dict
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.backend.detect import detect_changes
from app.backend.tiles import router as tiles_router

DB_PATH = "data/argus.db"

app = FastAPI(title="Argus Custode API", version="0.1.0")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount tiles router
app.include_router(tiles_router)


def init_db():
    os.makedirs("data", exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flights (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/")
def read_root():
    return {"name": "Argus Custode API", "status": "running"}


# Flight processing task
def process_flight_task(flight_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("UPDATE flights SET status = 'processing' WHERE id = ?", (flight_id,))
        conn.commit()

    try:
        # Default reference files
        before_path = "data/reference/before.tif"
        after_path = "data/reference/after.tif"

        if not os.path.exists(before_path) or not os.path.exists(after_path):
            raise FileNotFoundError("Reference GeoTIFFs not found")

        result = detect_changes(before_path, after_path)
        import json
        result_json = json.dumps(result)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "UPDATE flights SET status = 'done', result = ? WHERE id = ?",
                (result_json, flight_id),
            )
            conn.commit()
    except Exception as e:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                "UPDATE flights SET status = 'failed', result = ? WHERE id = ?",
                (str(e), flight_id),
            )
            conn.commit()


@app.post("/flights")
def create_flight(flight_data: Dict[str, Any] = None):
    import uuid
    flight_id = (flight_data or {}).get("id", str(uuid.uuid4())[:8])
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "INSERT OR REPLACE INTO flights (id, status) VALUES (?, ?)",
            (flight_id, "uploaded"),
        )
        conn.commit()
    return {"id": flight_id, "status": "uploaded"}


@app.post("/flights/{flight_id}/process")
def process_flight(flight_id: str, background_tasks: BackgroundTasks):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "INSERT OR REPLACE INTO flights (id, status) VALUES (?, ?)",
            (flight_id, "queued"),
        )
        conn.commit()
    background_tasks.add_task(process_flight_task, flight_id)
    return {"id": flight_id, "status": "queued"}


@app.get("/flights/{flight_id}/status")
def get_flight_status(flight_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.execute("SELECT status FROM flights WHERE id = ?", (flight_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Flight not found")
        return {"id": flight_id, "status": row[0]}


@app.get("/flights/{flight_id}/result")
def get_flight_result(flight_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.execute("SELECT status, result FROM flights WHERE id = ?", (flight_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Flight not found")
        status, result = row
        import json
        parsed_result = json.loads(result) if result and status == "done" else result
        return {"id": flight_id, "status": status, "result": parsed_result}
