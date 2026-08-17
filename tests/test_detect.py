import tempfile
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from app.backend.detect import detect_changes


def test_detect_changes_synthetic():
    # Create two temporary GeoTIFFs (64x64, 3 bands)
    transform = from_origin(-78.0, 0.0, 0.0001, 0.0001)
    profile = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'nodata': None,
        'width': 64,
        'height': 64,
        'count': 3,
        'crs': 'EPSG:4326',
        'transform': transform,
    }

    with tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as f_before, \
         tempfile.NamedTemporaryFile(suffix='.tif', delete=False) as f_after:
        before_path = f_before.name
        after_path = f_after.name

    try:
        # Before: baseline random texture
        data_before = np.random.randint(50, 100, (3, 64, 64), dtype=np.uint8)
        with rasterio.open(before_path, 'w', **profile) as dst:
            dst.write(data_before)

        # After: one patch strongly modified
        data_after = data_before.copy()
        data_after[:, 0:32, 0:32] = 250
        with rasterio.open(after_path, 'w', **profile) as dst:
            dst.write(data_after)

        result = detect_changes(before_path, after_path, patch=32, top_n=2)
        assert result['type'] == 'FeatureCollection'
        assert len(result['features']) == 2
        assert 'anomaly_score' in result['features'][0]['properties']
        assert result['features'][0]['geometry']['type'] == 'Polygon'
    finally:
        import os
        if os.path.exists(before_path):
            os.remove(before_path)
        if os.path.exists(after_path):
            os.remove(after_path)
