import numpy as np
import pytest
from app.backend.features import extract_features


def test_extract_features_shape():
    # 3 channels, 64x64 raster with patch=32 -> 2x2 = 4 patches
    raster = np.random.randint(0, 256, (3, 64, 64), dtype=np.uint8)
    features = extract_features(raster, patch=32)
    assert features.shape == (4, 12)
    assert np.isfinite(features).all()


def test_extract_features_constant():
    # Constant raster should have 0 variance and 0 gradient
    raster = np.full((3, 32, 32), 100, dtype=np.uint8)
    features = extract_features(raster, patch=32)
    assert features.shape == (1, 12)
    # Mean: 100, 100, 100
    np.testing.assert_allclose(features[0, :3], [100.0, 100.0, 100.0])
    # Var: 0, 0, 0
    np.testing.assert_allclose(features[0, 3:6], [0.0, 0.0, 0.0])
    # Gradients: 0
    np.testing.assert_allclose(features[0, 6:], 0.0)


def test_extract_features_small_raises():
    raster = np.zeros((3, 16, 16), dtype=np.uint8)
    with pytest.raises(ValueError):
        extract_features(raster, patch=32)
