"""Main FastAPI application for Argus Custode with asynchronous flight processing."""

from contextlib import asynccontextmanager
import json
import os
import logging
import sqlite3
import uuid
from typing import Any, Dict, List, Optional
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.backend.detect import detect_changes
from app.backend.ingest import validate_flight_photos
from app.backend.sites import build_router as build_sites_router, init_site_tables
from app.backend.tiles import router as tiles_router

# Testele importau get_db si scriau in baza de date de productie, lasand un zbor fantoma
# vizibil in API-ul public si, fiindca lista e ordonata dupa updated_at, chiar pe primul loc.
DB_PATH = os.environ.get("ARGUS_DB_PATH", "data/argus.db")


def flight_dir(flight_id: str, *parts: str) -> str:
    """Build a path inside data/flights/<flight_id>, refusing ids that escape it.

    flight_id arrives from the URL and was previously joined into a filesystem path
    unchecked; ".." or a separator would have written outside the flights directory.
    """
    if (
        not flight_id
        or flight_id in (".", "..")
        or os.path.basename(flight_id.replace("\\", "/")) != flight_id
    ):
        raise HTTPException(status_code=400, detail="Invalid flight id")
    return os.path.join("data", "flights", flight_id, *parts)


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
                validation TEXT,
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
            ("validation", "TEXT"),
            ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE flights ADD COLUMN {col_name} {col_def}")
        conn.commit()

    # Modelul de timeline: un sit are N capturi datate, iar o comparatie e intre oricare
    # doua. Vechiul model, in care un "zbor" era o PERECHE de rastere, forta exact doi
    # termeni de comparatie, alesi la incarcare.
    with get_db() as conn:
        init_site_tables(conn)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # In CI seed-ul ar descarca ortofotoplanul de referinta si ar construi COG-uri de ~11MB
    # la fiecare rulare, adica o dependenta de retea si minute irosite pentru date de care
    # testele nu au nevoie: benchmark-ul de detectie isi genereaza singur perechea.
    if os.environ.get("ARGUS_SKIP_SEED") == "1":
        logger.info("ARGUS_SKIP_SEED=1: se sare peste datele demo.")
        yield
        return

    try:
        from app.backend.provision import seed_demo_flight, seed_demo_site
        seed_demo_flight(get_db)
        seed_demo_site(get_db)
    except Exception as e:
        print(f"Demo seeding notice: {e}")
    yield


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Argus Custode API",
    description="Drone orthophoto change detection and tile server API",
    version="0.1.0",
    lifespan=lifespan,
)

# Enable CORS for web frontend clients
# allow_origins=["*"] impreuna cu allow_credentials=True nu trimite "*": Starlette
# REFLECTA Origin-ul care a cerut, cu Allow-Credentials: true. Adica orice pagina pe care
# o viziteaza utilizatorul putea sa scripteze backendul si sa citeasca raspunsurile.
# API-ul nu foloseste cookie-uri sau autentificare, deci nu are nevoie de credentiale.
_allowed = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount dynamic tile server router
app.include_router(tiles_router)

# Helperii de raster stau in main.py; importul lor din sites.py ar face un ciclu, deci se
# injecteaza la montare.
def _raster_bounds_of(path: str):
    from rasterio.warp import transform_bounds
    import rasterio

    if not path or not os.path.exists(path):
        return None
    try:
        with rasterio.open(path) as src:
            w, s_, e, n = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
            return [w, s_, e, n]
    except Exception as exc:
        logger.warning("Could not read bounds for %s: %s", path, exc)
        return None


def _site_helpers():
    from app.backend.provision import MAX_DEMO_DIM, build_cog, downsample_if_needed
    from app.backend.tiles import invalidate_layer_cache

    return {
        "build_cog": build_cog,
        "downsample_if_needed": downsample_if_needed,
        "max_dim": MAX_DEMO_DIM,
        "save_upload": save_upload,
        "max_raster_bytes": MAX_RASTER_BYTES,
        "invalidate_layer_cache": invalidate_layer_cache,
        "raster_bounds": _raster_bounds_of,
    }



@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"name": "Argus Custode API", "status": "running"}


def run_detection_job(flight_id: str, before_path: str, after_path: str, top_n: int = 50):
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

        # COG-urile se construiesc INAINTE de a marca done: un client care asteapta done si
        # apoi comuta harta prindea altfel un zbor fara tile-uri, pentru cateva secunde.
        cog_warning = None
        try:
            build_flight_cogs(flight_id, before_path, after_path)
        except Exception as cog_exc:
            # Detectia a reusit; lipsa tile-urilor nu face zborul un esec, dar nici nu se
            # trece sub tacere — altfel API-ul raporteaza succes cu harta goala.
            cog_warning = f"Detection succeeded but map imagery could not be prepared: {cog_exc}"
            logger.warning("COG build failed for flight %s: %s", flight_id, cog_exc)

        with get_db() as conn:
            conn.execute(
                """
                UPDATE flights
                SET status = 'done', result = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (result_json, cog_warning, flight_id),
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


def build_flight_cogs(flight_id: str, before_path: str, after_path: str):
    """Build tile-servable COGs for an uploaded flight, downsampling to fit memory."""
    from app.backend.provision import MAX_DEMO_DIM, build_cog, downsample_if_needed

    from app.backend.tiles import invalidate_layer_cache

    for layer, src in (("before", before_path), ("after", after_path)):
        dst = flight_dir(flight_id, f"{layer}.cog.tif")
        # Se reconstruieste cand sursa e mai noua. Varianta veche sarea peste orice COG
        # existent, deci dupa o corectie de imagini operatorul vedea rasterul VECHI cu
        # anomaliile NOI desenate peste, raportat ca status done.
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            continue
        # Handle-ul deschis din cache tine fisierul si il serveste in continuare; pe Windows
        # il face si nesters.
        invalidate_layer_cache(f"{flight_id}/{layer}")
        downsample_if_needed(src, MAX_DEMO_DIM)
        build_cog(src, dst)
        logger.info("Built %s", dst)


# Fara nicio limita, oricine putea umple discul unui serviciu public. Rasterele se citeau
# si integral in memorie, pe un tier de 512MB.
MAX_RASTER_BYTES = int(os.environ.get("MAX_RASTER_MB", "512")) * 1024 * 1024
MAX_PHOTO_BYTES = int(os.environ.get("MAX_PHOTO_MB", "64")) * 1024 * 1024


async def save_upload(upload: UploadFile, dest: str, max_bytes: int) -> str:
    """Stream an upload to disk, refusing anything over `max_bytes`."""
    written = 0
    try:
        with open(dest, "wb") as fh:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.",
                    )
                fh.write(chunk)
    except HTTPException:
        if os.path.exists(dest):
            os.remove(dest)
        raise
    return dest


def raster_bounds_wgs84(flight_id: str):
    """Geographic extent of a flight's imagery, as [west, south, east, north].

    The map needs it to clip tile requests, and the text equivalent needs it to anchor its
    zone grid: anchoring on the anomaly bounding box instead would make "zona de nord-vest"
    mean a different place on every flight.
    """
    from rasterio.warp import transform_bounds
    import rasterio

    candidates = (
        [os.path.join("data", "reference", "before.cog.tif")]
        if flight_id == "test"
        else [os.path.join("data", "flights", flight_id, "before.cog.tif")]
    )
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with rasterio.open(path) as src:
                w, s_, e, n = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
                return [w, s_, e, n]
        except Exception as exc:
            logger.warning("Could not read bounds for %s: %s", path, exc)
    return None


# Descrierile vin din generate_synthetic_pair, in engleza. Interfata e in romana, iar o
# voce sintetica romaneasca citeste "Structure removal" neinteligibil, deci se traduc aici,
# la sursa, in loc sa fie marcate lang="en" in frontend.
TRUTH_LABELS_RO = {
    "Structure removal": "Clădire demolată",
    "New blue structure/container": "Container albastru nou",
    "Vegetation clearing": "Defrișare de vegetație",
    "Excavation trench and mound": "Șanț de excavație",
}


@app.get("/flights/{flight_id}/truth")
def get_flight_truth(flight_id: str):
    """Known ground-truth changes for a flight, when the flight is a synthetic pair.

    Only the demo has this: its "after" raster was produced by injecting four changes into
    a copy of "before", so what changed is known exactly. A real flight has no such file,
    and saying so plainly is more useful than an empty collection that looks like "nothing
    changed here".
    """
    path = (
        os.path.join("data", "reference", "truth.geojson")
        if flight_id == "test"
        else flight_dir(flight_id, "truth.geojson")
    )
    if not os.path.exists(path):
        raise HTTPException(
            status_code=404,
            detail=f"Flight '{flight_id}' has no known ground truth; it is not a synthetic pair.",
        )

    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)

    for i, feature in enumerate(doc.get("features", []), start=1):
        props = feature.setdefault("properties", {})
        description = props.get("description", "")
        props["zone"] = i
        props["label"] = TRUTH_LABELS_RO.get(description, description)
    # "crs" a fost scos din RFC 7946; fisierul de pe disc il mai poarta.
    doc.pop("crs", None)
    return doc


@app.get("/flights")
def list_flights():
    """List every known flight, newest first, with what each one has available."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, status, before_path, after_path, error_message, updated_at,
                   result IS NOT NULL AS has_result,
                   validation IS NOT NULL AS has_validation
            FROM flights
            ORDER BY updated_at DESC
            """
        ).fetchall()

    flights = []
    for r in rows:
        fid = r["id"]
        flights.append({
            "bounds": raster_bounds_wgs84(fid),
            "id": fid,
            "status": r["status"],
            "updated_at": r["updated_at"],
            "has_result": bool(r["has_result"]),
            "has_validation": bool(r["has_validation"]),
            # Harta poate afisa zborul doar daca exista COG-urile lui, nu doar rasterele brute.
            # Anuntat in lista ca frontendul sa nu ceara un fisier despre care stie ca
            # lipseste: un 404 e o stare asteptata, dar tot polueaza consola browserului.
            "has_truth": os.path.exists(
                os.path.join("data", "reference", "truth.geojson")
                if fid == "test"
                else os.path.join("data", "flights", fid, "truth.geojson")
            ),
            "has_tiles": all(
                os.path.exists(os.path.join("data", "flights", fid, f"{layer}.cog.tif"))
                for layer in ("before", "after")
            ) or fid == "test",
        })
    return {"flights": flights}


@app.post("/flights")
async def upload_flight(
    flight_id: Optional[str] = Form(None),
    before: Optional[UploadFile] = File(None),
    after: Optional[UploadFile] = File(None),
):
    """Create a new flight entry with uploaded before and after GeoTIFFs."""
    fid = flight_id or f"flight_{uuid.uuid4().hex[:8]}"
    target_dir = flight_dir(fid)
    os.makedirs(target_dir, exist_ok=True)

    before_path = None
    after_path = None

    if before:
        before_path = await save_upload(before, os.path.join(target_dir, "before.tif"), MAX_RASTER_BYTES)

    if after:
        after_path = await save_upload(after, os.path.join(target_dir, "after.tif"), MAX_RASTER_BYTES)

    if not before_path and not after_path:
        # Fara asta, un singur POST fara fisiere si flight_id=test retrograda demo-ul public
        # la 'pending', ii stergea rezultatul si il lasa mort pana la repornire.
        raise HTTPException(
            status_code=400,
            detail="Provide at least one raster (before and/or after) when creating a flight.",
        )

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


@app.post("/flights/{flight_id}/photos")
async def upload_flight_photos(
    flight_id: str,
    files: List[UploadFile] = File(...),
):
    """Save raw drone flight photos into the flight photos directory."""
    photos_dir = flight_dir(flight_id, "photos")
    os.makedirs(photos_dir, exist_ok=True)

    saved_filenames: List[str] = []
    rejected: List[str] = []
    for file in files:
        raw_name = file.filename or ""
        cleaned = os.path.basename(raw_name.replace("\\", "/"))
        if not cleaned or cleaned in (".", ".."):
            safe_filename = f"photo_{uuid.uuid4().hex[:8]}.jpg"
        else:
            safe_filename = cleaned

        if not safe_filename.lower().endswith((".jpg", ".jpeg")):
            rejected.append(safe_filename)
            continue

        target_path = os.path.join(photos_dir, safe_filename)
        await save_upload(file, target_path, MAX_PHOTO_BYTES)
        saved_filenames.append(safe_filename)

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO flights (id, status)
            VALUES (?, 'pending')
            ON CONFLICT(id) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP
            """,
            (flight_id,),
        )
        conn.commit()

    return {
        "flight_id": flight_id,
        "saved": len(saved_filenames),
        "filenames": saved_filenames,
        # Se raporteaza explicit ce n-a fost acceptat: altfel clientul crede ca a incarcat
        # zece poze si a incarcat sapte.
        "rejected": rejected,
    }


@app.post("/flights/{flight_id}/validate")
def validate_flight(
    flight_id: str,
    min_blur_score: Optional[float] = None,
    min_overlap: Optional[float] = None,
    max_bad_fraction: Optional[float] = None,
):
    """Validate flight photos for blur, metadata, and coverage overlap."""
    with get_db() as conn:
        cursor = conn.execute("SELECT id FROM flights WHERE id = ?", (flight_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Flight '{flight_id}' not found")

    photos_dir = flight_dir(flight_id, "photos")
    if not os.path.exists(photos_dir):
        raise HTTPException(
            status_code=400,
            detail=f"No photos found for flight '{flight_id}'",
        )

    filenames = sorted([
        f for f in os.listdir(photos_dir)
        if os.path.isfile(os.path.join(photos_dir, f))
    ])
    if not filenames:
        raise HTTPException(
            status_code=400,
            detail=f"No photos found for flight '{flight_id}'",
        )

    paths = [os.path.join(photos_dir, f) for f in filenames]

    overrides: Dict[str, Any] = {}
    if min_blur_score is not None:
        overrides["min_blur_score"] = min_blur_score
    if min_overlap is not None:
        overrides["min_overlap"] = min_overlap
    if max_bad_fraction is not None:
        overrides["max_bad_fraction"] = max_bad_fraction

    report = validate_flight_photos(paths, **overrides)
    report_json = json.dumps(report)

    with get_db() as conn:
        conn.execute(
            """
            UPDATE flights
            SET validation = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (report_json, flight_id),
        )
        conn.commit()

    return report


@app.get("/flights/{flight_id}/validation")
def get_flight_validation(flight_id: str):
    """Retrieve saved validation report for a flight."""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id, validation FROM flights WHERE id = ?",
            (flight_id,),
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Flight '{flight_id}' not found")

    if not row["validation"]:
        raise HTTPException(
            status_code=404,
            detail=f"Flight '{flight_id}' has not been validated yet",
        )

    return json.loads(row["validation"])


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

    # Fall back only to THIS flight's own files on disk. Never to the demo reference
    # rasters: substituting them silently would report detections computed on somebody
    # else's imagery as if they were this flight's result.
    if not before_path or not os.path.exists(before_path):
        candidate = flight_dir(flight_id, "before.tif")
        before_path = candidate if os.path.exists(candidate) else None

    if not after_path or not os.path.exists(after_path):
        candidate = flight_dir(flight_id, "after.tif")
        after_path = candidate if os.path.exists(candidate) else None

    if not before_path or not after_path:
        missing = []
        if not before_path:
            missing.append("before.tif")
        if not after_path:
            missing.append("after.tif")
        raise HTTPException(
            status_code=400,
            detail=(
                f"Flight '{flight_id}' is missing {' and '.join(missing)}. "
                "Upload both rasters to POST /flights before processing."
            ),
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


# Montat la final: routerul primeste helperi (save_upload, limitele) definiti mai jos in
# acest fisier, deci montarea nu poate preceda definitiile lor.
app.include_router(build_sites_router(get_db, _site_helpers()))
