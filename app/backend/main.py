"""Main FastAPI application for Argus Custode with asynchronous flight processing."""

from contextlib import asynccontextmanager
import json
import os
import sqlite3
import uuid
from typing import Any, Dict, Optional
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.backend.detect import detect_changes
from app.backend.tiles import router as tiles_router

DB_PATH = "data/argus.db"


def get_db() -> sqlite3.Connection:
    """Create a thread-safe SQLite connection with WAL journal mode enabled."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database schema and ensure all required columns exist."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS flights (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                before_path TEXT,
                after_path TEXT,
                result TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor = conn.execute("PRAGMA table_info(flights)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        for col_name, col_def in [
            ("before_path", "TEXT"),
            ("after_path", "TEXT"),
            ("result", "TEXT"),
            ("error_message", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE flights ADD COLUMN {col_name} {col_def}")
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        from app.backend.provision import seed_demo_flight
        seed_demo_flight(get_db)
    except Exception as e:
        print(f"Demo seeding notice: {e}")
    yield


app = FastAPI(
    title="Argus Custode API",
    description="Drone orthophoto change detection and tile server API",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for web frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount dynamic tile server router
app.include_router(tiles_router)


@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"name": "Argus Custode API", "status": "running"}


def run_detection_job(flight_id: str, before_path: str, after_path: str, top_n: int = 20):
    """Background task function executing change detection without blocking the main event loop."""
    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO flights (id, status, before_path, after_path)
                VALUES (?, 'running', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = 'running',
                    updated_at = CURRENT_TIMESTAMP
                """,
                (flight_id, before_path, after_path),
            )
            conn.commit()

        if not os.path.exists(before_path):
            raise FileNotFoundError(f"Baseline file not found: {before_path}")
        if not os.path.exists(after_path):
            raise FileNotFoundError(f"Comparison file not found: {after_path}")

        # Run anomaly detection
        detection_geojson = detect_changes(before_path, after_path, top_n=top_n)
        result_json = json.dumps(detection_geojson)

        with get_db() as conn:
            conn.execute(
                """
                UPDATE flights
                SET status = 'done', result = ?, error_message = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (result_json, flight_id),
            )
            conn.commit()

    except Exception as exc:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE flights
                SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (str(exc), flight_id),
            )
            conn.commit()


@app.post("/flights")
async def upload_flight(
    flight_id: Optional[str] = Form(None),
    before: Optional[UploadFile] = File(None),
    after: Optional[UploadFile] = File(None),
):
    """Create a new flight entry with uploaded before and after GeoTIFFs."""
    fid = flight_id or f"flight_{uuid.uuid4().hex[:8]}"
    flight_dir = os.path.join("data", "flights", fid)
    os.makedirs(flight_dir, exist_ok=True)

    before_path = None
    after_path = None

    if before:
        before_path = os.path.join(flight_dir, "before.tif")
        with open(before_path, "wb") as f:
            content = await before.read()
            f.write(content)

    if after:
        after_path = os.path.join(flight_dir, "after.tif")
        with open(after_path, "wb") as f:
            content = await after.read()
            f.write(content)

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO flights (id, status, before_path, after_path)
            VALUES (?, 'pending', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = 'pending',
                before_path = COALESCE(excluded.before_path, flights.before_path),
                after_path = COALESCE(excluded.after_path, flights.after_path),
                updated_at = CURRENT_TIMESTAMP
            """,
            (fid, before_path, after_path),
        )
        conn.commit()

    return {
        "id": fid,
        "status": "pending",
        "before_path": before_path,
        "after_path": after_path,
    }


@app.post("/flights/{flight_id}/process")
def process_flight(
    flight_id: str,
    background_tasks: BackgroundTasks,
    top_n: int = 20,
):
    """Start asynchronous change detection on flight GeoTIFFs."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, status, before_path, after_path FROM flights WHERE id = ?",
            (flight_id,),
        )
        row = cursor.fetchone()

    before_path = row["before_path"] if row else None
    after_path = row["after_path"] if row else None

    # Check defaults if not set in DB
    if not before_path or not os.path.exists(before_path):
        flight_before = os.path.join("data", "flights", flight_id, "before.tif")
        if os.path.exists(flight_before):
            before_path = flight_before
        elif os.path.exists("data/reference/before.tif"):
            before_path = "data/reference/before.tif"

    if not after_path or not os.path.exists(after_path):
        flight_after = os.path.join("data", "flights", flight_id, "after.tif")
        if os.path.exists(flight_after):
            after_path = flight_after
        elif os.path.exists("data/reference/after.tif"):
            after_path = "data/reference/after.tif"

    if not before_path or not after_path:
        raise HTTPException(
            status_code=400,
            detail="Before or after raster files not found for this flight",
        )

    # Upsert flight record in database
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO flights (id, status, before_path, after_path)
            VALUES (?, 'pending', ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = 'pending',
                before_path = excluded.before_path,
                after_path = excluded.after_path,
                result = NULL,
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            """,
            (flight_id, before_path, after_path),
        )
        conn.commit()

    # Enqueue background detection task
    background_tasks.add_task(run_detection_job, flight_id, before_path, after_path, top_n)

    return {
        "id": flight_id,
        "status": "pending",
        "message": "Detection job queued successfully",
    }


@app.get("/flights/{flight_id}/status")
def get_flight_status(flight_id: str):
    """Retrieve current processing status for a flight."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, status, error_message, updated_at FROM flights WHERE id = ?",
            (flight_id,),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Flight '{flight_id}' not found")

    return {
        "id": row["id"],
        "status": row["status"],
        "error_message": row["error_message"],
        "updated_at": row["updated_at"],
    }


@app.get("/flights/{flight_id}/result")
def get_flight_result(flight_id: str):
    """Retrieve GeoJSON detection result for a finished flight."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, status, result, error_message FROM flights WHERE id = ?",
            (flight_id,),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Flight '{flight_id}' not found")

    status = row["status"]
    if status == "pending" or status == "running":
        return JSONResponse(
            status_code=202,
            content={
                "id": flight_id,
                "status": status,
                "message": "Processing in progress, result not ready yet",
            },
        )
    elif status == "failed":
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {row['error_message']}",
        )

    parsed_geojson = json.loads(row["result"]) if row["result"] else None
    return {
        "id": flight_id,
        "status": "done",
        "result": parsed_geojson,
    }
