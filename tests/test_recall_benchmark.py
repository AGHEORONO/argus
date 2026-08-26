"""Detection quality, measured on a self-contained scene so CI can actually run it.

The existing recall test uses the downloaded reference orthophoto and skips when it is
absent — which in CI means it never runs, and a skipped test is indistinguishable from a
passing one at a glance. That is how this project already shipped a blank tile server and
a detector that could not report "nothing changed": the suite was green either way.

So this benchmark builds its own before/after pair with a fixed seed, injects four changes
of different kinds at known coordinates, and measures how well the detector finds them.
No download, no skip, no external state.

It reports two numbers, and the second one is the sensitive one:

  * recall  — how many of the four injected changes appear at all
  * depth   — the worst rank at which one of them appears

Recall alone is a blunt instrument: it stays at 4/4 while quality quietly degrades. Depth
moves first. A change that used to surface at rank 6 and now surfaces at rank 40 is a real
regression that recall would not notice.
"""

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from app.backend.detect import detect_changes

PATCH = 32
SIZE = 512
TOP_N = 50

# Each zone is (row0, row1, col0, col1, description). Chosen to sit on patch boundaries so
# the test measures the detector, not the interaction between arbitrary offsets and the
# patch grid.
ZONES = [
    (64, 128, 64, 128, "structura demolata"),
    (160, 224, 288, 352, "obiect nou aparut"),
    (320, 384, 96, 160, "vegetatie indepartata"),
    (352, 448, 352, 416, "sant de excavatie"),
]


def _scene(rng):
    """A textured background that is neither flat nor pure noise.

    Pure noise makes every patch equally anomalous and the benchmark meaningless; a flat
    fill makes any change trivially detectable. Low-frequency structure plus fine grain is
    closer to what an orthophoto's feature distribution actually looks like.
    """
    ys, xs = np.mgrid[0:SIZE, 0:SIZE]
    base = (
        110
        + 28 * np.sin(xs / 47.0)
        + 22 * np.cos(ys / 61.0)
        + 12 * np.sin((xs + ys) / 29.0)
    )
    grain = rng.normal(0, 7, size=(SIZE, SIZE))
    band = np.clip(base + grain, 0, 255)
    img = np.stack([band, band * 0.94, band * 0.88]).astype(np.uint8)
    return img


def _inject(before, rng):
    """Apply the four changes, each with a different signature."""
    after = before.copy()

    # 1. Structure removed: replaced by uniform paving, so variance collapses.
    r0, r1, c0, c1, _ = ZONES[0]
    mean = before[:, r0:r1, c0:c1].mean(axis=(1, 2), keepdims=True)
    after[:, r0:r1, c0:c1] = np.clip(
        mean + rng.normal(0, 2, (3, r1 - r0, c1 - c0)), 0, 255
    ).astype(np.uint8)

    # 2. New object: strong, saturated, unlike anything around it.
    r0, r1, c0, c1, _ = ZONES[1]
    after[0, r0:r1, c0:c1] = 40
    after[1, r0:r1, c0:c1] = 90
    after[2, r0:r1, c0:c1] = 210

    # 3. Vegetation cleared: the subtle one. Green drops, texture smooths a little.
    r0, r1, c0, c1, _ = ZONES[2]
    patch = after[:, r0:r1, c0:c1].astype(np.float64)
    patch[1] *= 0.72
    patch[0] *= 1.06
    after[:, r0:r1, c0:c1] = np.clip(patch, 0, 255).astype(np.uint8)

    # 4. Trench: a dark linear cut with a bright spoil heap beside it.
    r0, r1, c0, c1, _ = ZONES[3]
    mid = (c0 + c1) // 2
    after[:, r0:r1, c0:mid] = np.clip(
        after[:, r0:r1, c0:mid].astype(np.float64) * 0.45, 0, 255
    ).astype(np.uint8)
    after[:, r0:r1, mid:c1] = np.clip(
        after[:, r0:r1, mid:c1].astype(np.float64) * 1.35, 0, 255
    ).astype(np.uint8)
    return after


def _write(path, arr):
    transform = from_origin(26.10, 44.42, 0.00002, 0.00002)
    with rasterio.open(
        path, "w", driver="GTiff", height=SIZE, width=SIZE, count=3,
        dtype="uint8", crs="EPSG:4326", transform=transform,
    ) as dst:
        dst.write(arr)


@pytest.fixture(scope="module")
def detection(tmp_path_factory):
    """Build the pair once and detect once; every assertion reads the same run."""
    rng = np.random.default_rng(20260826)
    before = _scene(rng)
    after = _inject(before, rng)

    folder = tmp_path_factory.mktemp("recall")
    before_path = str(folder / "before.tif")
    after_path = str(folder / "after.tif")
    _write(before_path, before)
    _write(after_path, after)

    result = detect_changes(before_path, after_path, patch=PATCH, top_n=TOP_N)
    return result


def _hits(result):
    """For each injected zone, the best (lowest) rank that overlaps it. None if missed."""
    found = {}
    for zone in ZONES:
        r0, r1, c0, c1, name = zone
        best = None
        for feature in result["features"]:
            pr0, pr1, pc0, pc1 = feature["properties"]["pixel_bounds"]
            if pr0 < r1 and pr1 > r0 and pc0 < c1 and pc1 > c0:
                rank = feature["properties"]["rank"]
                if best is None or rank < best:
                    best = rank
        found[name] = best
    return found


def test_recall_and_depth(detection, capsys):
    """The benchmark itself. Numbers are printed so CI logs carry the trend, not just a
    green tick — a run that still passes at 4/4 but at twice the depth is worth seeing."""
    found = _hits(detection)
    recall = sum(1 for v in found.values() if v is not None)
    depth = max((v for v in found.values() if v is not None), default=None)

    # Fara diacritice in diagnostice, deliberat: pe o consola cp1252 (Windows) un print cu
    # diacritice arunca UnicodeEncodeError si testul pica din motive care n-au nicio legatura
    # cu calitatea detectiei. In textul livrat utilizatorului diacriticele raman obligatorii.
    with capsys.disabled():
        print("\n  recall benchmark (seed 20260826, top_n=%d)" % TOP_N)
        for name, rank in found.items():
            print("    %-24s %s" % (name, f"rang {rank}" if rank else "NEGASIT"))
        print("    recall %d/%d, adancime maxima %s" % (recall, len(ZONES), depth))

    # Pragurile sunt santinele, nu obiective: la scrierea testului valorile masurate erau
    # recall 4/4 si adancime 10. Marja e ~2x, suficienta ca sa nu palpaie, destul de stransa
    # cat sa prinda o degradare reala. Daca se schimba detectorul si cifrele se muta legitim,
    # se ACTUALIZEAZA pragurile deliberat -- nu se sterge testul.
    assert recall == len(ZONES), f"recall a scăzut la {recall}/{len(ZONES)}: {found}"
    assert depth is not None and depth <= 20, (
        f"toate schimbările sunt găsite, dar prea adânc în clasament (rang {depth}, "
        "măsurat 10 la scrierea testului). Recall-ul singur nu ar fi observat asta."
    )


def test_detector_is_deterministic(detection, tmp_path):
    """Same input, same output. Without a fixed random_state the benchmark would drift and
    every threshold in this file would be meaningless."""
    rng = np.random.default_rng(20260826)
    before = _scene(rng)
    after = _inject(before, rng)
    b = str(tmp_path / "b.tif")
    a = str(tmp_path / "a.tif")
    _write(b, before)
    _write(a, after)

    again = detect_changes(b, a, patch=PATCH, top_n=TOP_N)
    first = [(f["properties"]["rank"], f["properties"]["patch_index"]) for f in detection["features"]]
    second = [(f["properties"]["rank"], f["properties"]["patch_index"]) for f in again["features"]]
    assert first == second


def test_unchanged_scene_reports_nothing(tmp_path):
    """The floor of the benchmark: if the detector reports changes on an identical pair,
    every recall number above is meaningless."""
    rng = np.random.default_rng(20260826)
    before = _scene(rng)
    b = str(tmp_path / "same_b.tif")
    a = str(tmp_path / "same_a.tif")
    _write(b, before)
    _write(a, before)

    result = detect_changes(b, a, patch=PATCH, top_n=TOP_N)
    assert result["features"] == []


def test_precision_is_reported(detection, capsys):
    """How many of the returned candidates land on a real change. Not asserted tightly —
    patches are a fixed grid and a large change spans several — but a collapse here means
    the detector started returning noise."""
    hit = 0
    for feature in detection["features"]:
        pr0, pr1, pc0, pc1 = feature["properties"]["pixel_bounds"]
        if any(pr0 < r1 and pr1 > r0 and pc0 < c1 and pc1 > c0 for r0, r1, c0, c1, _ in ZONES):
            hit += 1
    total = len(detection["features"])
    ratio = hit / total if total else 0

    with capsys.disabled():
        print("    precizie %d/%d candidati pe o schimbare reala (%.0f%%)" % (hit, total, ratio * 100))

    # Masurat 100% la scrierea testului. Pragul lasa loc pentru zgomot legitim, dar prinde
    # un detector care a inceput sa intoarca gunoi.
    assert ratio >= 0.6, f"doar {ratio:.0%} dintre candidați cad pe o schimbare reală"
