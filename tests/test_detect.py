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
        # `len(features) == top_n` was the old assertion here: a restatement of the
        # argument, which passed even with after == before. What matters is WHERE the
        # detection landed, so assert that instead.
        assert result['features'], 'no detection on a patch changed to solid 250'
        assert 'anomaly_score' in result['features'][0]['properties']
        assert result['features'][0]['geometry']['type'] == 'Polygon'

        r0, r1, c0, c1 = result['features'][0]['properties']['pixel_bounds']
        assert r0 < 32 and c0 < 32, (
            f'top detection at rows {r0}-{r1}, cols {c0}-{c1}; '
            'the modified patch is rows 0-32, cols 0-32'
        )
    finally:
        import os
        if os.path.exists(before_path):
            os.remove(before_path)
        if os.path.exists(after_path):
            os.remove(after_path)
