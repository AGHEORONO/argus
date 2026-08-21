"""Change detection using Isolation Forest on raster patch difference features."""

from typing import Any, Dict, List, Optional
import numpy as np
import rasterio
from rasterio.transform import xy
from rasterio.windows import Window
from shapely.geometry import Polygon, mapping
from sklearn.ensemble import IsolationForest

from app.backend.features import extract_features

# Cate randuri de patch-uri citim odata: mentine memoria per fasie mica (zeci de MB)
# in loc sa incarcam rasterul intreg (~335MB pentru before.tif la rezolutia demo).
STRIP_PATCH_ROWS = 64


def _extract_features_streamed(path: str, patch: int) -> np.ndarray:
    """Read a raster in horizontal strips aligned to the patch grid and extract features
    per strip, concatenating results - never holds the full raster array in memory."""
    with rasterio.open(path) as src:
        n_w = src.width // patch
        n_h = src.height // patch
        strip_rows = STRIP_PATCH_ROWS * patch

        chunks = []
        for row0 in range(0, n_h * patch, strip_rows):
            rows = min(strip_rows, n_h * patch - row0)
            window = Window(0, row0, n_w * patch, rows)
            chunks.append(extract_features(src.read(window=window), patch=patch))

        return np.concatenate(chunks, axis=0)


def detect_changes(
    before_path: str,
    after_path: str,
    patch: int = 32,
    top_n: int = 50,
    max_samples: int = 10000,
    n_estimators: int = 100,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Detect anomalous change candidates between two rasters using Isolation Forest on difference features.

    Args:
        before_path: Filepath to reference baseline GeoTIFF.
        after_path: Filepath to comparison GeoTIFF.
        patch: Spatial patch size in pixels.
        top_n: Number of top anomalous candidates to return.
        max_samples: Subsample size for fitting Isolation Forest.
        n_estimators: Number of trees in Isolation Forest.
        random_state: Random seed for reproducibility.

    Returns:
        GeoJSON FeatureCollection dictionary containing top_n anomalous patch polygons
        with anomaly scores and metadata.
    """
    with rasterio.open(before_path) as src_before:
        transform = src_before.transform
        crs = src_before.crs
        width = src_before.width

    # Extract patch features for both rasters, streamed in row-strips (nu tot rasterul
    # deodata) - vezi _extract_features_streamed, necesar pentru Render free tier (512MB).
    X_before = _extract_features_streamed(before_path, patch)
    X_after = _extract_features_streamed(after_path, patch)

    n_w = width // patch
    n_patches = len(X_before)

    # Compute pairwise difference features: unchanged patches form the normal inlier distribution (~0),
    # while changed areas produce outlier vectors in feature space.
    X_diff = np.abs(X_after - X_before)

    # Train Isolation Forest on difference feature space
    clf = IsolationForest(
        n_estimators=n_estimators,
        max_samples=min(max_samples, n_patches),
        random_state=random_state,
        n_jobs=-1,
    )
    clf.fit(X_diff)

    # Score samples on difference features (lower score_samples means more anomalous/isolated)
    raw_scores = clf.score_samples(X_diff)
    # Negate so higher anomaly_score means more anomalous
    anomaly_scores = -raw_scores

    # Rank patches by anomaly score descending
    sorted_indices = np.argsort(anomaly_scores)[::-1]
    top_indices = sorted_indices[:top_n]

    features: List[Dict[str, Any]] = []
    for rank, idx in enumerate(top_indices, start=1):
        row_idx = int(idx // n_w)
        col_idx = int(idx % n_w)

        r0 = row_idx * patch
        r1 = r0 + patch
        c0 = col_idx * patch
        c1 = c0 + patch

        x0, y0 = xy(transform, r0, c0, offset="ul")
        x1, y1 = xy(transform, r1, c1, offset="ul")

        poly = Polygon([
            (x0, y0),
            (x1, y0),
            (x1, y1),
            (x0, y1),
            (x0, y0),
        ])

        feature = {
            "type": "Feature",
            "id": f"anomaly_{rank}",
            "properties": {
                "rank": rank,
                "anomaly_score": float(anomaly_scores[idx]),
                "patch_index": int(idx),
                "pixel_bounds": [r0, r1, c0, c1],
            },
            "geometry": mapping(poly),
        }
        features.append(feature)

    crs_name = crs.to_string() if crs else "EPSG:4326"
    geojson_doc = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {
                "name": crs_name,
            },
        },
        "features": features,
    }

    return geojson_doc
