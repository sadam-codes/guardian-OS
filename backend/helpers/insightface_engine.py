"""InsightFace buffalo_l — detection + 512-d ArcFace embeddings."""

from __future__ import annotations

import logging
import os
import threading
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
FACE_MODELS_ROOT = Path(
    os.environ.get("INSIGHTFACE_MODELS_ROOT", _BACKEND_ROOT / "face_models")
)
BUFFALO_L_DIR = FACE_MODELS_ROOT / "buffalo_l"
BUFFALO_L_ZIP_URL = (
    "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
)
REQUIRED_ONNX = ("det_10g.onnx", "w600k_r50.onnx")

_app = None
_app_lock = threading.Lock()
_models_ready = False
_models_lock = threading.Lock()


class InsightFaceEngineError(Exception):
    pass


def _models_present() -> bool:
    return all((BUFFALO_L_DIR / name).is_file() for name in REQUIRED_ONNX)


def ensure_buffalo_l_models() -> None:
    global _models_ready
    with _models_lock:
        if _models_ready and _models_present():
            return
        BUFFALO_L_DIR.mkdir(parents=True, exist_ok=True)
        if _models_present():
            _models_ready = True
            return

        zip_path = FACE_MODELS_ROOT / "buffalo_l.zip"
        logger.info("Downloading InsightFace buffalo_l models (~275 MB)...")
        chunk_size = 1 << 20
        req = Request(BUFFALO_L_ZIP_URL, headers={"User-Agent": "guardian-os-face/1.0"})
        try:
            with urlopen(req, timeout=120) as resp:
                with open(zip_path, "wb") as out:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        out.write(chunk)
        except (OSError, HTTPError, URLError, TimeoutError) as exc:
            raise InsightFaceEngineError(
                "Could not download face models. Check your internet connection."
            ) from exc

        with zipfile.ZipFile(zip_path, "r") as archive:
            for name in REQUIRED_ONNX:
                try:
                    archive.extract(name, BUFFALO_L_DIR)
                except KeyError as exc:
                    raise InsightFaceEngineError(
                        f"Model pack missing {name}. Re-download buffalo_l."
                    ) from exc

        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass

        if not _models_present():
            raise InsightFaceEngineError("Face models failed to install.")
        _models_ready = True
        logger.info("InsightFace buffalo_l models ready at %s", BUFFALO_L_DIR)


def _get_face_analysis():
    global _app
    with _app_lock:
        if _app is not None:
            return _app
        ensure_buffalo_l_models()
        try:
            from insightface.app import FaceAnalysis
        except ImportError as exc:
            raise InsightFaceEngineError(
                "InsightFace is not installed. Run: pip install insightface onnxruntime"
            ) from exc

        ctx_id = int(os.environ.get("INSIGHTFACE_CTX_ID", "-1"))
        det_size = int(os.environ.get("INSIGHTFACE_DET_SIZE", "640"))
        app = FaceAnalysis(name="buffalo_l", root=str(FACE_MODELS_ROOT))
        app.prepare(ctx_id=ctx_id, det_size=(det_size, det_size))
        _app = app
        return _app


def extract_normed_embedding(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise InsightFaceEngineError("Invalid image. Use JPG or PNG.")

    app = _get_face_analysis()
    faces = app.get(bgr)
    if not faces:
        raise InsightFaceEngineError("No face detected. Face the camera clearly.")

    face = max(
        faces,
        key=lambda f: float((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])),
    )
    embedding = face.normed_embedding
    if embedding is None and face.embedding is not None:
        norm = np.linalg.norm(face.embedding)
        if norm > 0:
            embedding = face.embedding / norm
    if embedding is None:
        raise InsightFaceEngineError("Could not extract face embedding.")

    return np.asarray(embedding, dtype=np.float64)
