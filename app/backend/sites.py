"""Sites, dated captures, and comparisons between any two of them.

The original model made a "flight" mean *a pair of rasters*, which forced every comparison
to be exactly two epochs chosen at upload time. A surveying company flies the same site
repeatedly and wants to see progression, so the pair is the wrong unit.

Here a **capture** is one flight: one raster, one date. A **site** groups captures over
time. A **comparison** is a detection run between any two captures of the same site. That
also makes the photo-ingestion flow fit naturally — a set of photos produces one capture,
not a pair.

The older `/flights` endpoints are untouched and keep serving the demo.
"""

import json
import os
import sqlite3
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.backend.detect import detect_changes

DATA_DIR = os.path.join("data", "sites")


def init_site_tables(conn: sqlite3.Connection) -> None:
    """Create the timeline tables. Called from the same init path as the flights table."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS captures (
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            captured_on DATE NOT NULL,
            label TEXT,
            raster_path TEXT,
            cog_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (site_id) REFERENCES sites(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS comparisons (
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            base_capture TEXT NOT NULL,
            target_capture TEXT NOT NULL,
            status TEXT NOT NULL,
            result TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # One stored detection per ordered pair: re-running a comparison should update the
    # existing row rather than pile up copies that disagree with each other.
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_comparison_pair
        ON comparisons (site_id, base_capture, target_capture)
        """
    )
    conn.commit()


def safe_id(value: str, what: str) -> str:
    """Reject ids that would escape their directory once joined into a path."""
    if (
        not value
        or value in (".", "..")
        or os.path.basename(value.replace("\\", "/")) != value
    ):
        raise HTTPException(status_code=400, detail=f"Invalid {what} id")
    return value


def site_dir(site_id: str, *parts: str) -> str:
    return os.path.join(DATA_DIR, safe_id(site_id, "site"), *parts)


def parse_capture_date(value: str) -> str:
    """Accept an ISO date and store it normalised, so ordering is chronological.

    Stored as text: SQLite has no date type, and ISO-8601 sorts correctly as a string.
    A free-form date would break the timeline ordering silently.
    """
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"captured_on must be an ISO date such as 2026-08-25, got {value!r}",
        )


def build_router(get_db, flight_helpers: Dict[str, Any]) -> APIRouter:
    """Build the router with the database accessor injected.

    `get_db` and the raster helpers live in main.py; importing them here would create a
    cycle, so they are passed in when the router is mounted.
    """
    r = APIRouter()
    build_cog = flight_helpers["build_cog"]
    downsample_if_needed = flight_helpers["downsample_if_needed"]
    max_dim = flight_helpers["max_dim"]
    save_upload = flight_helpers["save_upload"]
    max_raster_bytes = flight_helpers["max_raster_bytes"]
    invalidate_layer_cache = flight_helpers["invalidate_layer_cache"]
    raster_bounds = flight_helpers["raster_bounds"]

    def row_to_capture(row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "site_id": row["site_id"],
            "captured_on": row["captured_on"],
            "label": row["label"],
            "has_tiles": bool(row["cog_path"] and os.path.exists(row["cog_path"])),
        }

    @r.post("/sites")
    def create_site(site_id: str = Form(...), name: str = Form(None)):
        """Register a monitored location."""
        sid = safe_id(site_id, "site")
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO sites (id, name) VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET name = COALESCE(excluded.name, sites.name)
                """,
                (sid, name or sid),
            )
            conn.commit()
        os.makedirs(site_dir(sid), exist_ok=True)
        return {"id": sid, "name": name or sid}

    @r.get("/sites")
    def list_sites():
        """Every site, with how many captures it has and the span they cover."""
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.name, s.created_at,
                       COUNT(c.id) AS capture_count,
                       MIN(c.captured_on) AS first_capture,
                       MAX(c.captured_on) AS last_capture
                FROM sites s
                LEFT JOIN captures c ON c.site_id = s.id
                GROUP BY s.id
                ORDER BY s.created_at DESC
                """
            ).fetchall()
        return {
            "sites": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "capture_count": row["capture_count"],
                    "first_capture": row["first_capture"],
                    "last_capture": row["last_capture"],
                }
                for row in rows
            ]
        }

    # ── Captures ─────────────────────────────────────────────────────────────────────

    @r.post("/sites/{site_id}/captures")
    async def add_capture(
        site_id: str,
        background_tasks: BackgroundTasks,
        captured_on: str = Form(...),
        label: Optional[str] = Form(None),
        raster: UploadFile = File(...),
    ):
        """Add one dated raster to a site's timeline."""
        sid = safe_id(site_id, "site")
        when = parse_capture_date(captured_on)

        with get_db() as conn:
            exists = conn.execute("SELECT id FROM sites WHERE id = ?", (sid,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Site '{sid}' not found")

        capture_id = f"{when}_{uuid.uuid4().hex[:6]}"
        folder = site_dir(sid, capture_id)
        os.makedirs(folder, exist_ok=True)
        raster_path = os.path.join(folder, "raster.tif")
        await save_upload(raster, raster_path, max_raster_bytes)

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO captures (id, site_id, captured_on, label, raster_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (capture_id, sid, when, label, raster_path),
            )
            conn.commit()

        # Tiles are what makes a capture viewable at all, so the COG is built eagerly in the
        # background rather than waiting for someone to run a comparison.
        background_tasks.add_task(prepare_capture_tiles, sid, capture_id, raster_path)

        return {
            "id": capture_id,
            "site_id": sid,
            "captured_on": when,
            "label": label,
            "has_tiles": False,
        }

    def prepare_capture_tiles(site_id: str, capture_id: str, raster_path: str) -> None:
        cog_path = site_dir(site_id, capture_id, "raster.cog.tif")
        try:
            if not os.path.exists(cog_path) or os.path.getmtime(cog_path) < os.path.getmtime(raster_path):
                invalidate_layer_cache(f"{site_id}/{capture_id}")
                downsample_if_needed(raster_path, max_dim)
                build_cog(raster_path, cog_path)
            with get_db() as conn:
                conn.execute("UPDATE captures SET cog_path = ? WHERE id = ?", (cog_path, capture_id))
                conn.commit()
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            with get_db() as conn:
                conn.execute("UPDATE captures SET cog_path = NULL WHERE id = ?", (capture_id,))
                conn.commit()
            raise RuntimeError(f"Could not prepare tiles for {capture_id}: {exc}") from exc

    @r.get("/sites/{site_id}/captures")
    def list_captures(site_id: str):
        """A site's timeline, oldest first — the order a timeline control needs."""
        sid = safe_id(site_id, "site")
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM captures WHERE site_id = ? ORDER BY captured_on ASC, id ASC",
                (sid,),
            ).fetchall()
        captures = [row_to_capture(row) for row in rows]
        for cap, row in zip(captures, rows):
            cap["bounds"] = raster_bounds(row["cog_path"]) if row["cog_path"] else None
        return {"site_id": sid, "captures": captures}

    # ── Comparisons ──────────────────────────────────────────────────────────────────

    def run_comparison(comparison_id: str, base_path: str, target_path: str, top_n: int) -> None:
        try:
            geojson = detect_changes(base_path, target_path, top_n=top_n)
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE comparisons
                    SET status = 'done', result = ?, error_message = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (json.dumps(geojson), comparison_id),
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001
            with get_db() as conn:
                conn.execute(
                    """
                    UPDATE comparisons
                    SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (str(exc), comparison_id),
                )
                conn.commit()

    @r.post("/sites/{site_id}/comparisons")
    def start_comparison(
        site_id: str,
        background_tasks: BackgroundTasks,
        base: str = Form(...),
        target: str = Form(...),
        top_n: int = Form(50),
    ):
        """Compare any two captures of the same site."""
        sid = safe_id(site_id, "site")
        if base == target:
            raise HTTPException(
                status_code=400,
                detail="A capture cannot be compared with itself; pick two different dates.",
            )

        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM captures WHERE site_id = ? AND id IN (?, ?)",
                (sid, base, target),
            ).fetchall()
        found = {row["id"]: row for row in rows}
        missing = [cid for cid in (base, target) if cid not in found]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Capture(s) not found in site '{sid}': {', '.join(missing)}",
            )

        # Chronological order decides which is the baseline, regardless of argument order:
        # otherwise the same pair could be stored twice with opposite meanings.
        pair = sorted(found.values(), key=lambda row: (row["captured_on"], row["id"]))
        base_row, target_row = pair[0], pair[1]

        for row in (base_row, target_row):
            if not row["raster_path"] or not os.path.exists(row["raster_path"]):
                raise HTTPException(
                    status_code=400,
                    detail=f"Capture '{row['id']}' has no raster on disk.",
                )

        comparison_id = f"cmp_{uuid.uuid4().hex[:8]}"
        with get_db() as conn:
            existing = conn.execute(
                """
                SELECT id FROM comparisons
                WHERE site_id = ? AND base_capture = ? AND target_capture = ?
                """,
                (sid, base_row["id"], target_row["id"]),
            ).fetchone()
            if existing:
                comparison_id = existing["id"]
                conn.execute(
                    """
                    UPDATE comparisons
                    SET status = 'running', result = NULL, error_message = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (comparison_id,),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO comparisons
                        (id, site_id, base_capture, target_capture, status)
                    VALUES (?, ?, ?, ?, 'running')
                    """,
                    (comparison_id, sid, base_row["id"], target_row["id"]),
                )
            conn.commit()

        background_tasks.add_task(
            run_comparison, comparison_id, base_row["raster_path"], target_row["raster_path"], top_n
        )
        return {
            "id": comparison_id,
            "site_id": sid,
            "base_capture": base_row["id"],
            "target_capture": target_row["id"],
            "status": "running",
        }

    @r.get("/comparisons/{comparison_id}")
    def get_comparison(comparison_id: str):
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM comparisons WHERE id = ?", (comparison_id,)
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Comparison '{comparison_id}' not found")
        return {
            "id": row["id"],
            "site_id": row["site_id"],
            "base_capture": row["base_capture"],
            "target_capture": row["target_capture"],
            "status": row["status"],
            "error_message": row["error_message"],
            "result": json.loads(row["result"]) if row["result"] else None,
        }

    @r.get("/sites/{site_id}/comparisons")
    def list_comparisons(site_id: str):
        """Every comparison for a site, so the UI can tell which steps are already computed."""
        sid = safe_id(site_id, "site")
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, base_capture, target_capture, status, updated_at,
                       result IS NOT NULL AS has_result
                FROM comparisons WHERE site_id = ?
                ORDER BY updated_at DESC
                """,
                (sid,),
            ).fetchall()
        return {
            "site_id": sid,
            "comparisons": [
                {
                    "id": row["id"],
                    "base_capture": row["base_capture"],
                    "target_capture": row["target_capture"],
                    "status": row["status"],
                    "has_result": bool(row["has_result"]),
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ],
        }

    return r
