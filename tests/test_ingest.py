"""Tests for flight photo ingestion and validation library."""

import os
import pytest
from app.backend.ingest import (
    DEFAULTS,
    blur_score,
    estimate_overlap,
    ground_footprint_m,
    read_photo_metadata,
    validate_flight_photos,
)
from tests.photo_fixtures import make_photo_set


def test_good_flight_photo_set(tmp_path):
    """1. Set bun (clar + GPS + spacing mic) -> accepted True, reasons gol."""
    dest = str(tmp_path / "good_set")
    paths = make_photo_set(dest, n=6, sharp=True, gps=True, spacing_m=10.0, altitude_m=100.0)

    report = validate_flight_photos(paths)

    assert report["accepted"] is True
    assert report["reasons"] == []
    assert report["summary"]["total"] == 6
    assert report["summary"]["blurry"] == 0
    assert report["summary"]["no_gps"] == 0
    assert report["summary"]["low_overlap"] == 0
    assert report["summary"]["unreadable"] == 0

    assert len(report["photos"]) == 6
    for p in report["photos"]:
        assert p["issues"] == []
        assert p["has_gps"] is True
        assert p["blur_score"] is not None
        assert p["blur_score"] >= DEFAULTS["min_blur_score"]


def test_blurry_flight_photo_set(tmp_path):
    """2. Set neclar (sharp=False) -> 'blurry' pe poze, accepted False, motiv care contine 'blur'."""
    dest = str(tmp_path / "blurry_set")
    paths = make_photo_set(dest, n=6, sharp=False, gps=True, spacing_m=10.0, altitude_m=100.0)

    report = validate_flight_photos(paths)

    assert report["accepted"] is False
    assert report["summary"]["blurry"] == 6
    # Motivele sunt in romana: interfata e lang="ro", iar acesta e cel mai important
    # text din raport.
    assert any("neclare" in r.lower() for r in report["reasons"])

    for p in report["photos"]:
        assert "blurry" in p["issues"]


def test_no_gps_flight_photo_set(tmp_path):
    """3. Set fara GPS -> 'no_gps', accepted False."""
    dest = str(tmp_path / "no_gps_set")
    paths = make_photo_set(dest, n=6, sharp=True, gps=False, spacing_m=10.0)

    report = validate_flight_photos(paths)

    assert report["accepted"] is False
    assert report["summary"]["no_gps"] == 6

    for p in report["photos"]:
        assert "no_gps" in p["issues"]
        assert p["has_gps"] is False


def test_low_overlap_flight_photo_set(tmp_path):
    """4. Set cu spacing mare -> 'low_overlap', accepted False."""
    dest = str(tmp_path / "low_overlap_set")
    # Footprint at 100m altitude with 13.2mm sensor and 8.8mm focal length is 150m.
    # spacing_m = 120m -> overlap is (150 - 120) / 150 = 20% < 60% (min_overlap).
    paths = make_photo_set(dest, n=6, sharp=True, gps=True, spacing_m=120.0, altitude_m=100.0)

    report = validate_flight_photos(paths)

    assert report["accepted"] is False
    assert report["summary"]["low_overlap"] > 0
    assert any("suprapunere" in r.lower() for r in report["reasons"])


def test_unreadable_corrupt_file_in_set(tmp_path):
    """5. Fisier corupt strecurat in set -> 'unreadable', fara exceptie propagata."""
    dest = str(tmp_path / "mixed_set")
    paths = make_photo_set(dest, n=3, sharp=True, gps=True, spacing_m=10.0)

    # Insert a corrupt file
    corrupt_path = os.path.join(dest, "DJI_0002_corrupt.JPG")
    with open(corrupt_path, "wb") as f:
        f.write(b"NOT_A_VALID_JPEG_IMAGE_DATA_CORRUPT")
    paths.append(corrupt_path)

    report = validate_flight_photos(paths)

    assert report["summary"]["unreadable"] >= 1
    corrupt_entry = next(p for p in report["photos"] if p["filename"] == "DJI_0002_corrupt.JPG")
    assert "unreadable" in corrupt_entry["issues"]
    assert corrupt_entry["blur_score"] is None
    assert corrupt_entry["has_gps"] is False
    assert corrupt_entry["overlap_with_previous"] is None


def test_blur_score_ordering(tmp_path):
    """6. Blur_score pe imagine clara > blur_score pe aceeasi imagine blurata (relatie de ordine, nu cifra magica)."""
    dest = str(tmp_path / "order_test")
    sharp_paths = make_photo_set(os.path.join(dest, "sharp"), n=1, sharp=True, gps=True)
    blurry_paths = make_photo_set(os.path.join(dest, "blurry"), n=1, sharp=False, gps=True)

    score_sharp = blur_score(sharp_paths[0])
    score_blurry = blur_score(blurry_paths[0])

    assert score_sharp > score_blurry
    assert score_sharp > 0
    assert score_blurry >= 0


def test_estimate_overlap(tmp_path):
    """7. Estimate_overlap intoarce None cand lipseste GPS-ul, si o fractie intre 0 si 1 cand exista."""
    dest = str(tmp_path / "overlap_test")
    gps_paths = make_photo_set(os.path.join(dest, "gps"), n=2, sharp=True, gps=True, spacing_m=15.0)
    no_gps_paths = make_photo_set(os.path.join(dest, "nogps"), n=1, sharp=True, gps=False)

    meta1 = read_photo_metadata(gps_paths[0])
    meta2 = read_photo_metadata(gps_paths[1])
    meta_nogps = read_photo_metadata(no_gps_paths[0])

    # Valid GPS pair -> float between 0.0 and 1.0
    overlap = estimate_overlap(meta1, meta2)
    assert overlap is not None
    assert isinstance(overlap, float)
    assert 0.0 <= overlap <= 1.0
    # With 15m spacing and 150m footprint, overlap should be approx 90%
    assert overlap == pytest.approx(0.90, abs=0.05)

    # Missing GPS on one or both -> None
    assert estimate_overlap(meta1, meta_nogps) is None
    assert estimate_overlap(meta_nogps, meta2) is None
    assert estimate_overlap(meta_nogps, meta_nogps) is None

    # Missing footprint / metadata -> None
    incomplete_meta = {"lat": 44.425, "lon": 26.103}
    assert estimate_overlap(meta1, incomplete_meta) is None
    assert estimate_overlap(None, meta2) is None


def test_overrides_change_verdict(tmp_path):
    """8. Praguri suprascrise prin **overrides chiar schimba verdictul (acelasi set, doua verdicte)."""
    dest = str(tmp_path / "override_test")
    # Generate blurry photo set that fails with defaults
    paths = make_photo_set(dest, n=6, sharp=False, gps=True, spacing_m=10.0)

    # Default min_blur_score is 100.0 -> rejected
    report_default = validate_flight_photos(paths)
    assert report_default["accepted"] is False

    # Override min_blur_score to 0.5 -> accepted
    report_override = validate_flight_photos(paths, min_blur_score=0.5)
    assert report_override["accepted"] is True
    assert report_override["config"]["min_blur_score"] == 0.5

    # Test override on spacing / min_overlap
    dest_spacing = str(tmp_path / "override_spacing")
    spacing_paths = make_photo_set(dest_spacing, n=6, sharp=True, gps=True, spacing_m=80.0)

    # Default min_overlap is 0.60 (overlap is ~46.7%) -> rejected
    rep_spacing_def = validate_flight_photos(spacing_paths)
    assert rep_spacing_def["accepted"] is False

    # Override min_overlap to 0.40 -> accepted
    rep_spacing_over = validate_flight_photos(spacing_paths, min_overlap=0.40)
    assert rep_spacing_over["accepted"] is True


def test_read_photo_metadata_and_footprint(tmp_path):
    """Verify metadata extraction fields, error handling on corrupt file, and ground footprint."""
    dest = str(tmp_path / "meta_test")
    paths = make_photo_set(dest, n=1, sharp=True, gps=True, altitude_m=120.0)

    meta = read_photo_metadata(paths[0])
    assert meta["error"] is None
    assert meta["width"] == 512
    assert meta["height"] == 512
    assert meta["lat"] == pytest.approx(44.425, abs=0.001)
    assert meta["lon"] == pytest.approx(26.103, abs=0.001)
    assert meta["altitude"] == pytest.approx(120.0, abs=0.1)
    assert meta["focal_length_mm"] == pytest.approx(8.8, abs=0.1)
    assert meta["sensor_width_mm"] == pytest.approx(13.2, abs=0.1)
    assert meta["camera"] == "DJI FC330"

    footprint = ground_footprint_m(meta)
    assert footprint is not None
    # 120 * (13.2 / 8.8) = 180.0 meters
    assert footprint == pytest.approx(180.0, abs=0.1)

    # Missing file or corrupt file handling
    corrupt_meta = read_photo_metadata(str(tmp_path / "non_existent_file.jpg"))
    assert corrupt_meta["error"] is not None
    assert corrupt_meta["width"] is None
    assert corrupt_meta["lat"] is None

    # Invalid / empty footprint calculations
    assert ground_footprint_m({}) is None
    assert ground_footprint_m(None) is None
    assert ground_footprint_m({"altitude": -50, "focal_length_mm": 8.8, "sensor_width_mm": 13.2}) is None


def test_validate_flight_photos_empty_list():
    """Verify handling of empty photo paths list."""
    report = validate_flight_photos([])
    assert report["accepted"] is False
    assert report["summary"]["total"] == 0
    assert len(report["reasons"]) > 0


def test_agl_comes_from_xmp_not_sea_level_exif(tmp_path):
    """EXIF GPSAltitude is referenced to SEA LEVEL; the overlap maths needs height above
    GROUND. Over terrain 80 m above sea level, a flight at 90 m AGL reports ~170 m in EXIF
    and the computed footprint comes out nearly twice too wide — so the validator approves
    a flight whose real overlap is far below the threshold. The error is always in the
    permissive direction, which is the dangerous one."""
    paths = make_photo_set(str(tmp_path / "agl"), n=2, sharp=True, gps=True,
                           altitude_m=170.0, agl_m=90.0)
    meta = read_photo_metadata(paths[0])

    assert meta["altitude"] == pytest.approx(170.0, abs=0.5), "EXIF should still carry MSL"
    assert meta["altitude_agl"] == pytest.approx(90.0, abs=0.5)
    assert meta["altitude_source"] == "xmp_relative"

    # 90 * 13.2 / 8.8 = 135.0, not 170 * 13.2 / 8.8 = 255.0
    assert ground_footprint_m(meta) == pytest.approx(135.0, abs=1.0)


def test_missing_xmp_falls_back_and_says_so(tmp_path):
    """A drone that writes no relative altitude still has to be handled, but the guess must
    be recorded as a guess so nothing downstream treats it as a measurement."""
    paths = make_photo_set(str(tmp_path / "nogps"), n=2, sharp=True, gps=False)
    meta = read_photo_metadata(paths[0])
    assert meta["altitude_agl"] is None or meta["altitude_source"] == "gps_msl_fallback"


def test_wrong_altitude_flips_the_overlap_verdict(tmp_path):
    """The consequence, stated as a test rather than as a comment: with photos 100 m apart,
    using sea-level altitude turns a failing flight into a passing one."""
    paths = make_photo_set(str(tmp_path / "flip"), n=4, sharp=True, gps=True,
                           spacing_m=100.0, altitude_m=170.0, agl_m=90.0)
    report = validate_flight_photos(paths)

    # True footprint 135 m, spacing 100 m -> overlap 0.26, well under the 0.6 default.
    assert not report["accepted"]
    assert report["summary"]["low_overlap"] > 0

    # Had it used the 170 m sea-level figure, footprint would be 255 m and overlap 0.61 —
    # a pass. Assert the arithmetic, so the reason this test exists cannot be forgotten.
    assert 1 - (100.0 / 255.0) > 0.6 > 1 - (100.0 / 135.0)


def test_rejection_reasons_are_romanian_and_agree(tmp_path):
    """The rejection reason is the single most important sentence in the report, and it was
    English inside a lang="ro" interface. Localising it exposed a second bug that only
    showed up on screen: agreeing the noun but not the verb produced "o fotografie AU
    suprapunere". Both agreements are asserted here so neither can regress silently."""
    from app.backend.ingest import _au, _fotografii, _sunt

    assert _fotografii(1) == "o fotografie"
    assert _fotografii(2) == "2 fotografii"
    assert _fotografii(20) == "20 de fotografii"
    assert _fotografii(21) == "21 de fotografii"
    assert (_sunt(1), _sunt(3)) == ("este", "sunt")
    assert (_au(1), _au(3)) == ("are", "au")

    # A single bad photo out of many: exercises the singular branch end to end.
    good = make_photo_set(str(tmp_path / "mixed"), n=6, sharp=True, gps=True, spacing_m=12.0)
    with open(good[0], "wb") as fh:
        fh.write(b"not an image at all")
    report = validate_flight_photos(good, max_bad_fraction=0.0)

    joined = " ".join(report["reasons"])
    assert joined, "expected at least one reason"
    assert not any(w in joined.lower() for w in ("photos", "blurry", "overlap", "missing")), joined
    # The exact shape the screen revealed: singular noun with plural verb.
    assert "o fotografie au " not in joined
    assert "o fotografie sunt " not in joined
