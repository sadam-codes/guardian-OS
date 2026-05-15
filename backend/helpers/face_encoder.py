import json

import cv2
import numpy as np

FACE_SIZE = (128, 128)
MATCH_THRESHOLD = 0.42


class FaceEncoderError(Exception):
    pass


_face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def image_bytes_to_bgr(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FaceEncoderError("Invalid image file. Use JPG or PNG.")
    return bgr


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm


def extract_face_encoding(image_bytes: bytes) -> list[float]:
    bgr = image_bytes_to_bgr(image_bytes)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = _face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))

    if len(faces) == 0:
        raise FaceEncoderError("No face detected. Use a clear front-facing photo.")

    if len(faces) > 1:
        raise FaceEncoderError("Multiple faces detected. Only one person per image.")

    x, y, w, h = faces[0]
    face = gray[y : y + h, x : x + w]
    face = cv2.resize(face, FACE_SIZE)
    vector = _normalize_vector(face.astype(np.float64).flatten())
    return vector.tolist()


def encoding_to_json(encoding: list[float]) -> str:
    return json.dumps(encoding)


def encoding_from_json(raw: str) -> np.ndarray:
    return np.array(json.loads(raw), dtype=np.float64)


def face_distance(known: np.ndarray, unknown: np.ndarray) -> float:
    known_n = _normalize_vector(known)
    unknown_n = _normalize_vector(unknown)
    return float(1.0 - np.dot(known_n, unknown_n))


def is_match(distance: float) -> bool:
    return distance <= MATCH_THRESHOLD
