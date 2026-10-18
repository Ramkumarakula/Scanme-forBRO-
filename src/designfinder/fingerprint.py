"""Color-independent perceptual fingerprints for design images."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

_WORK_SIZE = 256
_DCT_SIZE = 32
_LOW_FREQ = 8  # keep the 8x8 lowest DCT frequencies, minus the DC term
SIGNATURE_LEN = _LOW_FREQ * _LOW_FREQ - 1


@dataclass(frozen=True)
class Fingerprint:
    """Unit-length DCT signatures, compared by cosine similarity.

    These are continuous rather than thresholded into pHash bits: clean line drawings
    have many near-zero coefficients whose bits flip on tiny noise.
    """
    edge: np.ndarray  # signature of the edge/line map
    tone: np.ndarray  # signature of the contrast-normalized grayscale image


def load_image(path: str | Path) -> np.ndarray:
    """Read an image as BGR, flattening transparency onto white.

    Uses imdecode because cv2.imread fails on non-ASCII Windows paths.
    """
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    if img.dtype != np.uint8:
        img = cv2.convertScaleAbs(img, alpha=255.0 / max(1, int(img.max())))
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        rgb = img[:, :, :3].astype(np.float32)
        img = (rgb * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)
    return img


def _crop_to_content(gray: np.ndarray) -> np.ndarray:
    """Trim the plain background around the design so margins don't affect the hash."""
    border = np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]])
    background = float(np.median(border))
    mask = (np.abs(gray.astype(np.int16) - background) > 25).astype(np.uint8)
    points = cv2.findNonZero(mask)
    if points is None:
        return gray
    x, y, w, h = cv2.boundingRect(points)
    if w < 8 or h < 8:
        return gray
    # Re-add a uniform margin: content touching the border makes the hash shift-sensitive.
    pad = max(w, h) // 10
    return cv2.copyMakeBorder(gray[y:y + h, x:x + w], pad, pad, pad, pad,
                              cv2.BORDER_CONSTANT, value=int(background))


def _normalize(img: np.ndarray) -> np.ndarray:
    gray = _crop_to_content(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    h, w = gray.shape
    scale = _WORK_SIZE / max(h, w)
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    gray = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _edges(gray: np.ndarray) -> np.ndarray:
    # Auto Canny thresholds around the median so different color schemes behave alike.
    median = float(np.median(gray))
    lower = int(max(0, 0.66 * median))
    upper = int(min(255, 1.33 * median))
    if upper - lower < 20:
        lower, upper = 50, 150
    edges = cv2.Canny(cv2.GaussianBlur(gray, (3, 3), 0), lower, upper)
    return cv2.dilate(edges, np.ones((3, 3), np.uint8))


def dct_signature(gray: np.ndarray) -> np.ndarray:
    """Low-frequency DCT coefficients without DC, scaled to unit length.

    Dropping DC removes overall brightness; inverting the image negates the
    signature, so |cosine| treats inverted colors as the same design.
    """
    small = cv2.resize(gray, (_DCT_SIZE, _DCT_SIZE), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(small.astype(np.float32))
    low = dct[:_LOW_FREQ, :_LOW_FREQ].flatten()[1:]
    norm = float(np.linalg.norm(low))
    return (low / norm if norm > 0 else low).astype(np.float32)


def fingerprint_image(img: np.ndarray) -> Fingerprint:
    gray = _normalize(img)
    return Fingerprint(edge=dct_signature(_edges(gray)), tone=dct_signature(gray))


def fingerprint_file(path: str | Path) -> Fingerprint:
    return fingerprint_image(load_image(path))
