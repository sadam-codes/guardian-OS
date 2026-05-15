import json

import cv2
import numpy as np

from helpers.insightface_engine import (
    InsightFaceEngineError,
    extract_normed_embedding,
)

BIOMETRIC_FACE = "face"
BIOMETRIC_EYE = "eye"
ENCODING_VERSION = 4
EYE_ENCODING_VERSION = 1

# ArcFace cosine similarity on L2-normalized 512-d vectors — LOGIN (strict)
LOGIN_MIN_SIMILARITY = 0.50
# If two accounts both pass LOGIN_MIN_SIMILARITY, best must win by this gap.
LOGIN_MIN_SIMILARITY_GAP = 0.06

# Signup duplicate: only block when similarity is identity-level (stops false “already Sadam” on strangers).
SIGNUP_DUPLICATE_FACE_MIN = 0.93
SIGNUP_DUPLICATE_FACE_GAP = 0.07

# MediaPipe landmark eye identity — LOGIN (strict)
LOGIN_MIN_EYE_SIMILARITY = 0.88

# Signup duplicate eyes (landmarks correlate across people; keep bar high)
SIGNUP_DUPLICATE_EYE_MIN = 0.96
SIGNUP_DUPLICATE_EYE_GAP = 0.05

ENCODING_SIZE = (128, 128)
LBP_GRID = (4, 4)
LBP_BINS = 32

_hog = cv2.HOGDescriptor((128, 128), (16, 16), (8, 8), (8, 8), 9, 1)

_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


class FaceEncoderError(Exception):
    pass


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def image_bytes_to_bgr(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FaceEncoderError("Invalid image. Use JPG or PNG.")
    return bgr


def encoding_to_json(encoding: list[float], biometric_type: str = BIOMETRIC_FACE) -> str:
    return json.dumps(
        {
            "type": biometric_type,
            "vector": encoding,
            "source": "insightface-buffalo_l",
            "version": ENCODING_VERSION,
        }
    )


def encoding_from_json(raw: str) -> tuple[str, np.ndarray, int]:
    data = json.loads(raw)
    if isinstance(data, dict) and "vector" in data:
        bio_type = data.get("type", BIOMETRIC_FACE)
        version = int(data.get("version", 1))
        return bio_type, np.array(data["vector"], dtype=np.float64), version
    return "legacy", np.array(data, dtype=np.float64), 1


def face_similarity(known: np.ndarray, unknown: np.ndarray) -> float:
    if known.shape != unknown.shape:
        return 0.0
    known_n = _normalize_vector(known)
    unknown_n = _normalize_vector(unknown)
    return float(max(0.0, np.dot(known_n, unknown_n)))


def passes_login_similarity(similarity: float) -> bool:
    return similarity >= LOGIN_MIN_SIMILARITY


def passes_login_eye_similarity(similarity: float) -> bool:
    return similarity >= LOGIN_MIN_EYE_SIMILARITY


def passes_login_face_ambiguity(best_similarity: float, second_similarity: float | None) -> bool:
    """Reject login when two enrolled faces score similarly (ambiguous winner)."""
    if second_similarity is None:
        return True
    if second_similarity < LOGIN_MIN_SIMILARITY:
        return True
    return (best_similarity - second_similarity) >= LOGIN_MIN_SIMILARITY_GAP


def eye_encoding_to_json(encoding: list[float]) -> str:
    return json.dumps(
        {
            "type": BIOMETRIC_EYE,
            "vector": encoding,
            "source": "mediapipe-face-landmarks",
            "version": EYE_ENCODING_VERSION,
        }
    )


def eye_encoding_from_json(raw: str) -> tuple[str, np.ndarray, int]:
    if not raw or not str(raw).strip():
        return BIOMETRIC_EYE, np.array([], dtype=np.float64), EYE_ENCODING_VERSION
    data = json.loads(raw)
    if isinstance(data, dict) and "vector" in data:
        bio_type = data.get("type", BIOMETRIC_EYE)
        version = int(data.get("version", EYE_ENCODING_VERSION))
        vec = np.array(data["vector"], dtype=np.float64)
        return bio_type, vec, version
    return BIOMETRIC_EYE, np.array([], dtype=np.float64), EYE_ENCODING_VERSION


def is_signup_duplicate_eye(
    best_similarity: float,
    second_similarity: float | None,
) -> bool:
    if best_similarity < SIGNUP_DUPLICATE_EYE_MIN:
        return False
    if second_similarity is None:
        return True
    return (best_similarity - second_similarity) >= SIGNUP_DUPLICATE_EYE_GAP


def is_signup_duplicate(
    best_similarity: float,
    second_similarity: float | None,
) -> bool:
    if best_similarity < SIGNUP_DUPLICATE_FACE_MIN:
        return False
    if second_similarity is None:
        return True
    return (best_similarity - second_similarity) >= SIGNUP_DUPLICATE_FACE_GAP


def _local_binary_pattern(gray: np.ndarray) -> np.ndarray:
    center = gray[1:-1, 1:-1]
    code = np.zeros(center.shape, dtype=np.uint8)
    neighbors = (
        gray[0:-2, 0:-2],
        gray[0:-2, 1:-1],
        gray[0:-2, 2:],
        gray[1:-1, 2:],
        gray[2:, 2:],
        gray[2:, 1:-1],
        gray[2:, 0:-2],
        gray[1:-1, 0:-2],
    )
    for i, neighbor in enumerate(neighbors):
        code |= (neighbor >= center).astype(np.uint8) << i
    return code


def _lbp_feature_vector(face_gray: np.ndarray) -> np.ndarray:
    face = cv2.resize(face_gray, ENCODING_SIZE)
    face = cv2.equalizeHist(face)
    lbp = _local_binary_pattern(face)
    grid_h, grid_w = LBP_GRID
    cell_h = max(1, lbp.shape[0] // grid_h)
    cell_w = max(1, lbp.shape[1] // grid_w)
    parts: list[np.ndarray] = []
    for row in range(grid_h):
        for col in range(grid_w):
            y1 = row * cell_h
            y2 = (row + 1) * cell_h if row < grid_h - 1 else lbp.shape[0]
            x1 = col * cell_w
            x2 = (col + 1) * cell_w if col < grid_w - 1 else lbp.shape[1]
            cell = lbp[y1:y2, x1:x2]
            hist, _ = np.histogram(cell.ravel(), bins=LBP_BINS, range=(0, 256))
            parts.append(hist.astype(np.float64))
    return _normalize_vector(np.concatenate(parts))


def _hog_feature_vector(face_gray: np.ndarray) -> np.ndarray:
    face = cv2.resize(face_gray, ENCODING_SIZE)
    face = cv2.equalizeHist(face)
    features = _hog.compute(face)
    if features is None:
        raise FaceEncoderError("Could not extract face features.")
    return _normalize_vector(features.flatten())


def _crop_largest_face(gray: np.ndarray) -> np.ndarray:
    faces = _face_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
    )
    if len(faces) == 0:
        raise FaceEncoderError("No face detected. Face the camera clearly.")

    x, y, w, h = max(faces, key=lambda f: int(f[2]) * int(f[3]))
    pad = int(max(w, h) * 0.12)
    y1 = max(0, y - pad)
    y2 = min(gray.shape[0], y + h + pad)
    x1 = max(0, x - pad)
    x2 = min(gray.shape[1], x + w + pad)
    face = gray[y1:y2, x1:x2]
    if face.size == 0:
        raise FaceEncoderError("Could not read face. Try again.")
    return face


def extract_face_encoding_v4(image_bytes: bytes) -> list[float]:
    try:
        return extract_normed_embedding(image_bytes).tolist()
    except InsightFaceEngineError as exc:
        raise FaceEncoderError(str(exc)) from exc


def extract_face_encoding_v3(image_bytes: bytes) -> list[float]:
    bgr = image_bytes_to_bgr(image_bytes)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    face = _crop_largest_face(gray)
    return _hog_feature_vector(face).tolist()


def extract_face_encoding_v2(image_bytes: bytes) -> list[float]:
    bgr = image_bytes_to_bgr(image_bytes)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    face = _crop_largest_face(gray)
    return _lbp_feature_vector(face).tolist()


def extract_face_encoding_legacy(image_bytes: bytes) -> list[float]:
    bgr = image_bytes_to_bgr(image_bytes)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    face = _crop_largest_face(gray)
    face = cv2.resize(face, ENCODING_SIZE)
    return _normalize_vector(face.astype(np.float64).flatten()).tolist()


def extract_face_encoding(image_bytes: bytes) -> list[float]:
    return extract_face_encoding_v4(image_bytes)


def extract_encoding_for_version(image_bytes: bytes, version: int) -> list[float]:
    if version == ENCODING_VERSION:
        return extract_face_encoding_v4(image_bytes)
    if version == 3:
        return extract_face_encoding_v3(image_bytes)
    if version == 2:
        return extract_face_encoding_v2(image_bytes)
    return extract_face_encoding_legacy(image_bytes)


def average_encodings(encodings: list[list[float]]) -> list[float]:
    if not encodings:
        raise FaceEncoderError("No face samples provided.")
    stacked = np.array(encodings, dtype=np.float64)
    return _normalize_vector(np.mean(stacked, axis=0)).tolist()


def average_eye_encodings(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        raise FaceEncoderError("No eye samples provided.")
    dim = len(vectors[0])
    if any(len(v) != dim for v in vectors):
        raise FaceEncoderError("Eye samples have inconsistent dimensions.")
    stacked = np.array(vectors, dtype=np.float64)
    return _normalize_vector(np.mean(stacked, axis=0)).tolist()


def build_probes_from_samples(
    samples: list[bytes],
    needed_versions: set[int] | None = None,
) -> dict[int, np.ndarray]:
    versions = needed_versions or {ENCODING_VERSION}
    probes: dict[int, np.ndarray] = {}

    if ENCODING_VERSION in versions:
        probes[ENCODING_VERSION] = np.array(
            average_encodings([extract_face_encoding_v4(s) for s in samples]),
            dtype=np.float64,
        )
    if 3 in versions:
        probes[3] = np.array(
            average_encodings([extract_face_encoding_v3(s) for s in samples]),
            dtype=np.float64,
        )
    if 2 in versions:
        probes[2] = np.array(
            average_encodings([extract_face_encoding_v2(s) for s in samples]),
            dtype=np.float64,
        )
    if 1 in versions:
        probes[1] = np.array(
            average_encodings([extract_face_encoding_legacy(s) for s in samples]),
            dtype=np.float64,
        )
    return probes


def extract_biometric_encoding(
    biometric_type: str,
    *,
    encoding_raw: str | None = None,
    image_bytes: bytes | None = None,
) -> list[float]:
    if image_bytes:
        return extract_face_encoding(image_bytes)
    raise FaceEncoderError("Camera image required.")


def extract_eye_encoding(image_bytes: bytes) -> list[float]:
    raise FaceEncoderError("Eye encoding is computed on the client (MediaPipe).")


def extract_palm_encoding(image_bytes: bytes) -> list[float]:
    return extract_face_encoding(image_bytes)
