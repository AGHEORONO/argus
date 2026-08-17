"""Feature extraction per patch for raster change detection."""

import numpy as np


def extract_features(raster: np.ndarray, patch: int = 32) -> np.ndarray:
    """Extract statistical and gradient features per spatial patch from a raster.

    Args:
        raster: NumPy array of shape (C, H, W) or (H, W).
        patch: Size of square spatial patch in pixels (default: 32).

    Returns:
        NumPy array of shape (n_patches, n_features) where:
        n_patches = (H // patch) * (W // patch)
        n_features = 4 * C (mean, variance, mean vertical gradient, mean horizontal gradient per channel).
    """
    if raster.ndim == 2:
        raster = raster[np.newaxis, ...]

    C, H, W = raster.shape
    n_h = H // patch
    n_w = W // patch
    n_patches = n_h * n_w

    if n_patches == 0:
        raise ValueError(f"Raster dimensions ({H}, {W}) are smaller than patch size {patch}")

    # Crop to exact multiples of patch size
    cropped = raster[:, : n_h * patch, : n_w * patch]

    # Vectorized reshaping without Python loops:
    # (C, n_h, patch, n_w, patch) -> (n_h, n_w, C, patch, patch) -> (n_patches, C, patch, patch)
    blocks = cropped.reshape(C, n_h, patch, n_w, patch).transpose(1, 3, 0, 2, 4).reshape(n_patches, C, patch, patch)

    # 1. Mean color per band
    mean_color = blocks.mean(axis=(-2, -1), dtype=np.float32)

    # 2. Local variance per band
    var_color = blocks.var(axis=(-2, -1), dtype=np.float32)

    # 3. Spatial gradients (Sobel / finite difference approximation)
    blocks_i16 = blocks.astype(np.int16)
    grad_y = np.abs(np.diff(blocks_i16, axis=-2)).mean(axis=(-2, -1), dtype=np.float32)
    grad_x = np.abs(np.diff(blocks_i16, axis=-1)).mean(axis=(-2, -1), dtype=np.float32)

    # Concatenate all features into (n_patches, n_features)
    features = np.concatenate([mean_color, var_color, grad_y, grad_x], axis=1)

    return features
