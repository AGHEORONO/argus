"""Flight photo ingestion and validation library for photogrammetry pipelines."""

import math
import os
from typing import Any, Dict, List, Optional
import numpy as np
from PIL import Image
from scipy.ndimage import laplace

# Praguri ca parametri cu valori implicite (regula din planul de implementare).
# Se pot suprascrie via **overrides in validate_flight_photos().
DEFAULTS = {
    "min_blur_score": 100.0,   # varianta Laplacianului; mai mare = mai clar
    "min_overlap": 0.60,       # fractie de suprapunere intre poze consecutive
    "max_bad_fraction": 0.20,  # peste atata poze problematice, setul e respins
    "max_dim": 1024,           # latura lunga la care se citeste imaginea pentru analiza
}


def _parse_dms(dms: Any, ref: Any) -> Optional[float]:
    """Parse GPS DMS (degrees, minutes, seconds) tuple or number to signed decimal degrees."""
    if dms is None:
        return None
    try:
        if isinstance(dms, (int, float)):
            val = float(dms)
        elif len(dms) == 3:
            deg = float(dms[0])
            minute = float(dms[1])
            sec = float(dms[2])
            val = deg + minute / 60.0 + sec / 3600.0
        elif len(dms) == 1:
            val = float(dms[0])
        else:
            return None

        if ref is not None:
            ref_str = str(ref).strip().upper()
            if ref_str in ("S", "W"):
                val = -abs(val)
            elif ref_str in ("N", "E"):
                val = abs(val)
        return float(val)
    except Exception:
        return None


def _parse_altitude(alt: Any, ref: Any) -> Optional[float]:
    """Parse GPS altitude value and altitude reference."""
    if alt is None:
        return None
    try:
        val = float(alt)
        if ref is not None and (ref == 1 or ref == b"\x01" or str(ref) == "1"):
            val = -abs(val)
        return float(val)
    except Exception:
        return None


def _parse_rational(val: Any) -> Optional[float]:
    """Parse rational numbers, floats, ints, or tuples to float."""
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, (tuple, list)):
            if len(val) == 2:
                return float(val[0]) / float(val[1]) if val[1] != 0 else None
            elif len(val) == 1:
                return float(val[0])
        return float(val)
    except Exception:
        return None


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return R * c


def _read_relative_altitude(img) -> Optional[float]:
    """Height above the launch point, in metres, from the drone's XMP block.

    This is the number the overlap maths actually needs. EXIF GPSAltitude is referenced to
    SEA LEVEL, so over terrain 80 m above sea level a flight at 90 m AGL reports ~170 m and
    the computed ground footprint comes out nearly twice too wide — which makes the
    validator approve a flight whose real overlap is far below the threshold. The error is
    always in the permissive direction, which is the dangerous one.

    DJI writes drone-dji:RelativeAltitude; Autel and Parrot use their own namespaces, so the
    search is by local tag name rather than by namespace.
    """
    try:
        xmp = img.getxmp()
    except Exception:
        return None
    if not xmp:
        return None

    wanted = ("relativealtitude", "aboveterrainaltitude", "gpsaltituderelative")

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key.split(":")[-1].lower() in wanted:
                    try:
                        # DJI writes a signed string such as "+50.30".
                        return float(str(value).lstrip("+"))
                    except (TypeError, ValueError):
                        pass
                found = walk(value)
                if found is not None:
                    return found
        elif isinstance(node, (list, tuple)):
            for item in node:
                found = walk(item)
                if found is not None:
                    return found
        return None

    value = walk(xmp)
    # A relative altitude at or below zero cannot produce a footprint.
    return value if value and value > 0 else None


def read_photo_metadata(path: str) -> dict:
    """Read photo metadata and EXIF tags without loading full image into memory.

    Args:
        path: Path to the image file.

    Returns:
        Dictionary with keys: 'path', 'filename', 'width', 'height', 'datetime',
        'lat', 'lon', 'altitude', 'focal_length_mm', 'sensor_width_mm', 'camera'.
        Missing values are None. On corrupt/unreadable files, 'error' is set and
        no exception is raised.
    """
    res: Dict[str, Any] = {
        "path": str(path),
        "filename": os.path.basename(path),
        "width": None,
        "height": None,
        "datetime": None,
        "lat": None,
        "lon": None,
        "altitude": None,
        # Kept apart deliberately: one is above sea level, the other above the ground, and
        # only the second one means anything for ground footprint.
        "altitude_agl": None,
        "altitude_source": None,
        "focal_length_mm": None,
        "sensor_width_mm": None,
        "camera": None,
        "error": None,
    }

    try:
        with Image.open(path) as img:
            res["width"] = int(img.width)
            res["height"] = int(img.height)

            exif = img.getexif()
            if not exif:
                return res

            # Camera make / model
            make = exif.get(0x010F)  # Make
            model = exif.get(0x0110)  # Model
            if isinstance(make, bytes):
                make = make.decode("utf-8", errors="ignore").rstrip("\x00")
            if isinstance(model, bytes):
                model = model.decode("utf-8", errors="ignore").rstrip("\x00")

            if make and model:
                s_make = str(make).strip()
                s_model = str(model).strip()
                if s_make.lower() in s_model.lower():
                    res["camera"] = s_model
                else:
                    res["camera"] = f"{s_make} {s_model}".strip()
            elif model:
                res["camera"] = str(model).strip()
            elif make:
                res["camera"] = str(make).strip()

            # DateTime
            dt = exif.get(0x0132)  # DateTime

            # Sub-IFDs: Exif IFD (0x8769) and GPS IFD (0x8825)
            exif_ifd = exif.get_ifd(0x8769)
            if exif_ifd:
                dt = exif_ifd.get(0x9003) or exif_ifd.get(0x9004) or dt
                focal = _parse_rational(exif_ifd.get(0x920A))  # FocalLength
                if focal is not None and focal > 0:
                    res["focal_length_mm"] = focal

                # Sensor width from FocalLengthIn35mmFilm or FocalPlaneXResolution
                focal_35 = _parse_rational(exif_ifd.get(0xA405))  # FocalLengthIn35mmFilm
                if focal and focal_35 and focal_35 > 0:
                    res["sensor_width_mm"] = 36.0 * (focal / focal_35)
                else:
                    x_res = _parse_rational(exif_ifd.get(0xA20E))  # FocalPlaneXResolution
                    unit = exif_ifd.get(0xA210)  # FocalPlaneResolutionUnit
                    if x_res and x_res > 0 and res["width"]:
                        if unit == 2:  # Inches
                            res["sensor_width_mm"] = (res["width"] / x_res) * 25.4
                        elif unit == 3:  # Centimeters
                            res["sensor_width_mm"] = (res["width"] / x_res) * 10.0
                        elif unit == 4:  # Millimeters
                            res["sensor_width_mm"] = res["width"] / x_res
                        elif unit == 5:  # Micrometers
                            res["sensor_width_mm"] = (res["width"] / x_res) * 0.001

            if dt:
                if isinstance(dt, bytes):
                    dt = dt.decode("utf-8", errors="ignore").rstrip("\x00")
                res["datetime"] = str(dt).strip()

            # GPS IFD
            gps_ifd = exif.get_ifd(0x8825)
            if gps_ifd:
                res["lat"] = _parse_dms(gps_ifd.get(2), gps_ifd.get(1))
                res["lon"] = _parse_dms(gps_ifd.get(4), gps_ifd.get(3))
                res["altitude"] = _parse_altitude(gps_ifd.get(6), gps_ifd.get(5))

            agl = _read_relative_altitude(img)
            if agl is not None:
                res["altitude_agl"] = agl
                res["altitude_source"] = "xmp_relative"
            elif res["altitude"] is not None:
                # Falling back to sea-level altitude is a guess, and it is recorded as one so
                # nothing downstream can mistake it for a measurement.
                res["altitude_agl"] = res["altitude"]
                res["altitude_source"] = "gps_msl_fallback"

    except Exception as e:
        res["error"] = str(e)

    return res


def blur_score(path: str, max_dim: int = 1024) -> float:
    """Compute blur score using variance of Laplacian on grayscale image.

    Args:
        path: Filepath to the image.
        max_dim: Maximum dimension on the long edge to resize for analysis.

    Returns:
        Variance of Laplacian. Higher values indicate sharper images.
    """
    with Image.open(path) as img:
        try:
            img.draft("L", (max_dim, max_dim))
        except Exception:
            pass

        gray = img.convert("L")
        w, h = gray.size
        long_dim = max(w, h)
        if long_dim > max_dim:
            scale = max_dim / long_dim
            new_w = max(1, round(w * scale))
            new_h = max(1, round(h * scale))
            gray = gray.resize((new_w, new_h), Image.Resampling.BILINEAR)

        arr = np.asarray(gray, dtype=np.float64)
        lap = laplace(arr)
        return float(lap.var())


def ground_footprint_m(meta: dict) -> Optional[float]:
    """Calculate ground width covered by photo in meters from altitude, focal length, and sensor width.

    Args:
        meta: Metadata dictionary containing 'altitude', 'focal_length_mm', and 'sensor_width_mm'.

    Returns:
        Ground footprint width in meters, or None if data is insufficient or invalid.
    """
    if not isinstance(meta, dict):
        return None

    # AGL when the drone recorded it; otherwise the sea-level value, flagged as a fallback.
    alt = meta.get("altitude_agl")
    if alt is None:
        alt = meta.get("altitude")
    focal = meta.get("focal_length_mm")
    sensor_w = meta.get("sensor_width_mm")

    if alt is None or focal is None or sensor_w is None:
        return None

    try:
        alt_f = float(alt)
        focal_f = float(focal)
        sensor_w_f = float(sensor_w)
        if alt_f <= 0 or focal_f <= 0 or sensor_w_f <= 0:
            return None
        return alt_f * (sensor_w_f / focal_f)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def estimate_overlap(meta_a: dict, meta_b: dict) -> Optional[float]:
    """Estimate overlap fraction between two consecutive photos from GPS distance and ground footprint.

    Args:
        meta_a: Metadata dict of first photo.
        meta_b: Metadata dict of second photo.

    Returns:
        Fraction between 0.0 and 1.0, or None if GPS or footprint cannot be calculated.
    """
    if not isinstance(meta_a, dict) or not isinstance(meta_b, dict):
        return None

    lat_a = meta_a.get("lat")
    lon_a = meta_a.get("lon")
    lat_b = meta_b.get("lat")
    lon_b = meta_b.get("lon")

    if lat_a is None or lon_a is None or lat_b is None or lon_b is None:
        return None

    footprint_a = ground_footprint_m(meta_a)
    footprint_b = ground_footprint_m(meta_b)

    if footprint_a is None or footprint_b is None:
        return None

    footprint = (footprint_a + footprint_b) / 2.0
    if footprint <= 0:
        return None

    try:
        dist = _haversine_distance(float(lat_a), float(lon_a), float(lat_b), float(lon_b))
        overlap = max(0.0, min(1.0, 1.0 - (dist / footprint)))
        return float(overlap)
    except Exception:
        return None


def _de(n: int) -> str:
    """Romanian numerals take the particle "de" when the last two digits are 0 or 20-99."""
    rest = abs(n) % 100
    return "de " if rest == 0 or rest >= 20 else ""


def _fotografii(n: int) -> str:
    if n == 1:
        return "o fotografie"
    return f"{n} {_de(n)}fotografii"


# Verbul trebuie sa se acorde si el, nu doar substantivul: "o fotografie AU suprapunere"
# e gresit, si exact asta a aparut in interfata cand se acorda doar substantivul.
def _sunt(n: int) -> str:
    return "este" if n == 1 else "sunt"


def _au(n: int) -> str:
    return "are" if n == 1 else "au"


def validate_flight_photos(paths: list[str], **overrides) -> dict:
    """Validate a set of flight photos for photogrammetry quality.

    Checks for image readability, blur/sharpness, presence of GPS coordinates,
    and consecutive photo overlap.

    Args:
        paths: List of file paths to the photos to validate.
        **overrides: Optional threshold overrides (min_blur_score, min_overlap,
            max_bad_fraction, max_dim).

    Returns:
        Validation report dictionary with structure:
        {
            'accepted': bool,
            'config': dict,
            'summary': {
                'total': int,
                'blurry': int,
                'no_gps': int,
                'low_overlap': int,
                'unreadable': int,
            },
            'reasons': list[str],
            'photos': list[dict],
        }
    """
    config = dict(DEFAULTS)
    config.update(overrides)

    min_blur_score = float(config.get("min_blur_score", DEFAULTS["min_blur_score"]))
    min_overlap = float(config.get("min_overlap", DEFAULTS["min_overlap"]))
    max_bad_fraction = float(config.get("max_bad_fraction", DEFAULTS["max_bad_fraction"]))
    max_dim = int(config.get("max_dim", DEFAULTS["max_dim"]))

    sorted_paths = sorted(paths, key=lambda p: (os.path.basename(p), p))

    if not sorted_paths:
        return {
            "accepted": False,
            "config": config,
            "summary": {
                "total": 0,
                "blurry": 0,
                "no_gps": 0,
                "low_overlap": 0,
                "unreadable": 0,
            },
            "reasons": ["No photos provided for validation."],
            "photos": [],
        }

    photos: List[Dict[str, Any]] = []
    prev_meta: Optional[Dict[str, Any]] = None

    for path in sorted_paths:
        filename = os.path.basename(path)
        issues: List[str] = []
        meta = read_photo_metadata(path)

        if meta.get("error") is not None:
            issues.append("unreadable")
            photos.append({
                "filename": filename,
                "blur_score": None,
                "has_gps": False,
                "overlap_with_previous": None,
                "issues": issues,
            })
            continue

        # Check GPS
        lat = meta.get("lat")
        lon = meta.get("lon")
        has_gps = (lat is not None and lon is not None)
        if not has_gps:
            issues.append("no_gps")

        # Check blur
        score: Optional[float] = None
        try:
            score = blur_score(path, max_dim=max_dim)
            if score < min_blur_score:
                issues.append("blurry")
        except Exception:
            score = None
            issues.append("unreadable")

        # Check overlap with previous readable photo
        overlap_prev: Optional[float] = None
        if prev_meta is not None:
            overlap_prev = estimate_overlap(prev_meta, meta)
            if overlap_prev is not None and overlap_prev < min_overlap:
                issues.append("low_overlap")

        photos.append({
            "filename": filename,
            "blur_score": score,
            "has_gps": has_gps,
            "overlap_with_previous": overlap_prev,
            "issues": issues,
        })

        prev_meta = meta

    total = len(photos)
    blurry_count = sum(1 for p in photos if "blurry" in p["issues"])
    no_gps_count = sum(1 for p in photos if "no_gps" in p["issues"])
    low_overlap_count = sum(1 for p in photos if "low_overlap" in p["issues"])
    unreadable_count = sum(1 for p in photos if "unreadable" in p["issues"])

    summary = {
        "total": total,
        "blurry": blurry_count,
        "no_gps": no_gps_count,
        "low_overlap": low_overlap_count,
        "unreadable": unreadable_count,
    }

    bad_photos_count = sum(1 for p in photos if len(p["issues"]) > 0)
    bad_fraction = bad_photos_count / total if total > 0 else 1.0

    if bad_photos_count == 0:
        accepted = True
        reasons = []
    elif bad_fraction > max_bad_fraction:
        accepted = False
        reasons = []
        # Localizate la sursa. Erau in engleza intr-o interfata romaneasca, iar acesta e
        # cel mai important text din tot raportul: propozitia care spune DE CE a fost
        # respins setul. O voce sintetica romaneasca citind engleza e neinteligibila, iar
        # marcarea lang="en" in frontend ar fi fost onesta dar tot inutilizabila.
        if blurry_count > 0:
            reasons.append(
                f"{_fotografii(blurry_count)} din {total} {_sunt(blurry_count)} neclare "
                f"(scor minim de claritate: {min_blur_score:.0f})"
            )
        if no_gps_count > 0:
            reasons.append(
                f"{_fotografii(no_gps_count)} din {total} nu {_au(no_gps_count)} coordonate GPS"
            )
        if low_overlap_count > 0:
            reasons.append(
                f"{_fotografii(low_overlap_count)} {_au(low_overlap_count)} suprapunere "
                f"insuficientă cu fotografia anterioară (minim {min_overlap:.0%})"
            )
        if unreadable_count > 0:
            reasons.append(
                f"{_fotografii(unreadable_count)} din {total} {_sunt(unreadable_count)} "
                f"corupte sau ilizibile"
            )
        if not reasons:
            reasons.append(
                f"{_fotografii(bad_photos_count)} din {total} ({bad_fraction:.0%}) "
                f"{_au(bad_photos_count)} probleme de calitate, peste pragul maxim de "
                f"{max_bad_fraction:.0%}"
            )
    else:
        accepted = True
        reasons = []

    return {
        "accepted": accepted,
        "config": config,
        "summary": summary,
        "reasons": reasons,
        "photos": photos,
    }
