"""Synthetic flight photo fixtures generator for testing ingestion and validation."""

import os
from typing import List
import numpy as np
from PIL import ExifTags, Image, ImageFilter


def make_photo_set(
    dest_dir: str,
    n: int = 6,
    sharp: bool = True,
    gps: bool = True,
    spacing_m: float = 10.0,
    altitude_m: float = 100.0,
    agl_m: float = None,
    terrain_m: float = 0.0,
) -> List[str]:
    """Generate synthetic JPEG flight photo files with EXIF metadata for testing.

    Args:
        dest_dir: Directory where JPEG photos will be created.
        n: Number of synthetic photos to generate.
        sharp: If True, generate sharp high-contrast images. If False, apply Gaussian blur.
        gps: If True, include EXIF GPS tags (lat, lon, altitude) and focal length.
        spacing_m: Distance in meters between consecutive photo positions along latitude.
        altitude_m: Height above sea level written to EXIF GPSAltitude, as a real drone does.
        agl_m: Height above ground written to the XMP block, as DJI does. When given, this
            is the number the overlap maths should use.
        terrain_m: Ground elevation above sea level; only used to make the two altitudes
            differ realistically when agl_m is not given explicitly.

    Returns:
        Sorted list of generated photo file paths.
    """
    os.makedirs(dest_dir, exist_ok=True)
    paths: List[str] = []
    base_lat = 44.425
    base_lon = 26.103
    meters_per_deg_lat = 111139.0

    for i in range(n):
        filename = f"DJI_{i+1:04d}.JPG"
        filepath = os.path.join(dest_dir, filename)

        rng = np.random.default_rng(1000 + i)
        arr = np.zeros((512, 512, 3), dtype=np.uint8)
        # Create high contrast sharp grid lines and geometric shapes
        arr[::16, :, :] = 255
        arr[:, ::16, :] = 255
        for _ in range(30):
            x0, y0 = rng.integers(0, 450, size=2)
            w, h = rng.integers(20, 60, size=2)
            c = rng.integers(0, 256, size=3)
            arr[y0 : y0 + h, x0 : x0 + w] = c

        img = Image.fromarray(arr, mode="RGB")

        if not sharp:
            img = img.filter(ImageFilter.GaussianBlur(radius=8))

        exif = img.getexif()
        exif[0x010F] = "DJI"
        exif[0x0110] = "FC330"
        exif[0x0132] = f"2026:08:25 10:00:{i:02d}"

        if gps:
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            # Focal length 8.8mm, 35mm equivalent 24mm -> sensor width 13.2mm
            # Footprint at 100m alt = 100 * (13.2 / 8.8) = 150m
            exif_ifd[0x920A] = 8.8
            exif_ifd[0xA405] = 24
            exif_ifd[0x9003] = f"2026:08:25 10:00:{i:02d}"

            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            lat_i = base_lat + i * (spacing_m / meters_per_deg_lat)
            lon_i = base_lon

            d_lat = int(abs(lat_i))
            rem_lat = (abs(lat_i) - d_lat) * 60.0
            m_lat = int(rem_lat)
            s_lat = (rem_lat - m_lat) * 60.0

            d_lon = int(abs(lon_i))
            rem_lon = (abs(lon_i) - d_lon) * 60.0
            m_lon = int(rem_lon)
            s_lon = (rem_lon - m_lon) * 60.0

            gps_ifd[1] = "N" if lat_i >= 0 else "S"
            gps_ifd[2] = (float(d_lat), float(m_lat), float(s_lat))
            gps_ifd[3] = "E" if lon_i >= 0 else "W"
            gps_ifd[4] = (float(d_lon), float(m_lon), float(s_lon))
            gps_ifd[5] = 0
            gps_ifd[6] = float(altitude_m)

        # Fara XMP nu se poate testa calea corecta: EXIF poarta altitudinea fata de nivelul
        # marii, iar suprapunerea are nevoie de cea fata de sol.
        agl = agl_m if agl_m is not None else max(0.0, altitude_m - terrain_m)
        xmp = (
            '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            '<rdf:Description rdf:about="" '
            'xmlns:drone-dji="http://www.dji.com/drone-dji/1.0/" '
            f'drone-dji:RelativeAltitude="+{agl:.2f}" '
            f'drone-dji:AbsoluteAltitude="+{altitude_m:.2f}"/>'
            '</rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
        )
        if gps:
            img.save(filepath, format="JPEG", exif=exif, xmp=xmp.encode("utf-8"))
        else:
            img.save(filepath, format="JPEG", exif=exif)
        paths.append(filepath)

    return sorted(paths)
