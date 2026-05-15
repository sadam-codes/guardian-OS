import json

import numpy as np
from sqlalchemy.orm import Session

from helpers.face_encoder import (
    BIOMETRIC_FACE,
    ENCODING_VERSION,
    FaceEncoderError,
    average_encodings,
    average_eye_encodings,
    build_probes_from_samples,
    encoding_from_json,
    encoding_to_json,
    extract_face_encoding,
    eye_encoding_from_json,
    eye_encoding_to_json,
    face_similarity,
    is_signup_duplicate,
    is_signup_duplicate_eye,
    passes_login_eye_similarity,
    passes_login_similarity,
)
from helpers.roles import ROLE_ADMIN, ROLE_USER, VALID_ROLES
from models.register import Register


class FaceAuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _parse_eye_vectors_json(raw: str | None) -> list[list[float]]:
    if raw is None or not str(raw).strip():
        raise FaceAuthError("Eye biometric data is required.", 400)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FaceAuthError("Invalid eye biometric payload.", 400) from exc
    if not isinstance(data, list) or len(data) == 0:
        raise FaceAuthError("Eye biometric data is required.", 400)
    out: list[list[float]] = []
    for item in data:
        if not isinstance(item, list) or len(item) < 8:
            raise FaceAuthError("Invalid eye sample in payload.", 400)
        try:
            out.append([float(x) for x in item])
        except (TypeError, ValueError) as exc:
            raise FaceAuthError("Invalid eye sample values.", 400) from exc
    return out


def _has_stored_eye(user: Register) -> bool:
    _, vec, _ = eye_encoding_from_json(user.eye_encoding)
    return vec.size > 0


def _versions_in_db(db: Session) -> set[int]:
    versions: set[int] = set()
    for user in db.query(Register).all():
        _, _, version = encoding_from_json(user.face_encoding)
        versions.add(version)
    return versions


def _probes_from_samples(db: Session, samples: list[bytes]) -> dict[int, np.ndarray]:
    versions = _versions_in_db(db) | {ENCODING_VERSION}
    try:
        return build_probes_from_samples(samples, versions)
    except FaceEncoderError as exc:
        raise FaceAuthError(str(exc)) from exc


def _score_all_users(
    db: Session, probes: dict[int, np.ndarray]
) -> list[tuple[Register, float, int]]:
    scores: list[tuple[Register, float, int]] = []
    for user in db.query(Register).all():
        _, known, version = encoding_from_json(user.face_encoding)
        probe = probes.get(version)
        if probe is None or known.shape != probe.shape:
            continue
        similarity = face_similarity(known, probe)
        if similarity > 0:
            scores.append((user, similarity, version))
    scores.sort(key=lambda item: item[1], reverse=True)
    return scores


def _resolve_login(scores: list[tuple[Register, float, int]]) -> tuple[Register, float, int]:
    if not scores:
        raise FaceAuthError("Face not recognized. Please sign up first.", 401)

    best_user, best_sim, best_version = scores[0]
    if not passes_login_similarity(best_sim):
        raise FaceAuthError("Face not recognized. Please sign up first.", 401)

    return best_user, best_sim, best_version


def _check_duplicate_face(db: Session, probes: dict[int, np.ndarray]) -> None:
    scores = [
        entry
        for entry in _score_all_users(db, probes)
        if entry[2] == ENCODING_VERSION
    ]
    if not scores:
        return
    best_user, best_sim, _ = scores[0]
    second_sim = scores[1][1] if len(scores) > 1 else None
    if is_signup_duplicate(best_sim, second_sim):
        raise FaceAuthError(
            f"This face is already registered as '{best_user.name}'. Use sign in instead.",
            409,
        )


def _check_duplicate_eye(db: Session, eye_probe: np.ndarray) -> None:
    scores: list[tuple[Register, float]] = []
    for user in db.query(Register).all():
        _, known, _ = eye_encoding_from_json(user.eye_encoding)
        if known.size == 0:
            continue
        if known.shape != eye_probe.shape:
            continue
        sim = face_similarity(known, eye_probe)
        if sim > 0:
            scores.append((user, sim))
    scores.sort(key=lambda item: item[1], reverse=True)
    if not scores:
        return
    best_user, best_sim = scores[0]
    second_sim = scores[1][1] if len(scores) > 1 else None
    if is_signup_duplicate_eye(best_sim, second_sim):
        raise FaceAuthError(
            f"This eye pattern is already registered as '{best_user.name}'. Sign in instead.",
            409,
        )


def _verify_login_eyes(db: Session, user: Register, eye_vectors: list[list[float]]) -> None:
    try:
        probe_list = average_eye_encodings(eye_vectors)
    except FaceEncoderError as exc:
        raise FaceAuthError(str(exc)) from exc
    probe = np.array(probe_list, dtype=np.float64)

    if _has_stored_eye(user):
        _, stored, _ = eye_encoding_from_json(user.eye_encoding)
        if stored.shape != probe.shape:
            raise FaceAuthError(
                "Stored eye template is incompatible. Ask an admin to update your profile.",
                401,
            )
        sim = face_similarity(stored, probe)
        if not passes_login_eye_similarity(sim):
            raise FaceAuthError(
                "Face matched but eyes did not verify. Look straight at the camera with both eyes visible.",
                401,
            )
        return

    user.eye_encoding = eye_encoding_to_json(probe_list)
    db.commit()
    db.refresh(user)


def _resolve_signup_role(db: Session, requested_role: str, actor_role: str | None) -> str:
    role = (requested_role or ROLE_USER).strip().lower()
    if role not in VALID_ROLES:
        raise FaceAuthError("Role must be 'admin' or 'user'.")
    if db.query(Register).count() == 0:
        return ROLE_ADMIN
    if role == ROLE_ADMIN and actor_role != ROLE_ADMIN:
        raise FaceAuthError("Only an admin can create admin accounts.", 403)
    return role


def signup_face(
    db: Session,
    name: str,
    image_bytes: bytes | None = None,
    image_bytes_list: list[bytes] | None = None,
    *,
    eye_encodings_json: str | None = None,
    role: str = ROLE_USER,
    actor_role: str | None = None,
    biometric_type: str = BIOMETRIC_FACE,
) -> Register:
    clean_name = name.strip()
    if not clean_name:
        raise FaceAuthError("Name is required.")

    samples = list(image_bytes_list or [])
    if image_bytes is not None:
        samples.insert(0, image_bytes)
    if not samples:
        raise FaceAuthError("Camera image required.")

    eye_vectors = _parse_eye_vectors_json(eye_encodings_json)
    if len(eye_vectors) != len(samples):
        raise FaceAuthError("Eye samples must match the number of face frames.", 400)

    probes = _probes_from_samples(db, samples)
    _check_duplicate_face(db, probes)

    try:
        eye_avg_list = average_eye_encodings(eye_vectors)
        eye_probe = np.array(eye_avg_list, dtype=np.float64)
    except FaceEncoderError as exc:
        raise FaceAuthError(str(exc)) from exc

    _check_duplicate_eye(db, eye_probe)

    user = Register(
        name=clean_name,
        face_encoding=encoding_to_json(
            average_encodings([extract_face_encoding(s) for s in samples]),
            BIOMETRIC_FACE,
        ),
        eye_encoding=eye_encoding_to_json(eye_avg_list),
        role=_resolve_signup_role(db, role, actor_role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_face(
    db: Session,
    image_bytes: bytes | None = None,
    image_bytes_list: list[bytes] | None = None,
    *,
    eye_encodings_json: str | None = None,
    biometric_type: str = BIOMETRIC_FACE,
) -> Register:
    samples = list(image_bytes_list or [])
    if image_bytes is not None:
        samples.insert(0, image_bytes)
    if not samples:
        raise FaceAuthError("Camera image required.", 400)

    eye_vectors = _parse_eye_vectors_json(eye_encodings_json)
    if len(eye_vectors) != len(samples):
        raise FaceAuthError("Eye samples must match the number of face frames.", 400)

    if not db.query(Register).count():
        raise FaceAuthError("No registered users. Sign up first.", 404)

    try:
        probes = _probes_from_samples(db, samples)
    except FaceEncoderError as exc:
        raise FaceAuthError(str(exc)) from exc

    scores = _score_all_users(db, probes)
    best_user, _, best_version = _resolve_login(scores)

    _verify_login_eyes(db, best_user, eye_vectors)

    if best_version != ENCODING_VERSION:
        try:
            upgraded = average_encodings([extract_face_encoding(s) for s in samples])
            best_user.face_encoding = encoding_to_json(upgraded, BIOMETRIC_FACE)
            db.commit()
            db.refresh(best_user)
        except FaceEncoderError:
            pass

    return best_user


def list_registered_users(db: Session) -> list[Register]:
    return db.query(Register).order_by(Register.name).all()


def _require_admin(actor_role: str | None) -> None:
    if actor_role != ROLE_ADMIN:
        raise FaceAuthError("Admin access required.", 403)


def _admin_count(db: Session) -> int:
    return db.query(Register).filter(Register.role == ROLE_ADMIN).count()


def get_user_by_id(db: Session, user_id: int) -> Register | None:
    return db.query(Register).filter(Register.id == user_id).first()


def update_user(
    db: Session,
    user_id: int,
    *,
    actor_role: str | None,
    name: str | None = None,
    role: str | None = None,
    image_bytes: bytes | None = None,
    biometric_type: str = BIOMETRIC_FACE,
) -> Register:
    _require_admin(actor_role)
    user = get_user_by_id(db, user_id)
    if user is None:
        raise FaceAuthError("User not found.", 404)

    if name is None and role is None and image_bytes is None:
        raise FaceAuthError("No changes provided.", 400)

    if name is not None:
        clean_name = name.strip()
        if not clean_name:
            raise FaceAuthError("Name is required.")
        user.name = clean_name

    if role is not None:
        new_role = role.strip().lower()
        if new_role not in VALID_ROLES:
            raise FaceAuthError("Role must be 'admin' or 'user'.")
        if user.role == ROLE_ADMIN and new_role == ROLE_USER and _admin_count(db) <= 1:
            raise FaceAuthError("Cannot remove the last administrator.", 400)
        user.role = new_role

    if image_bytes is not None:
        try:
            encoding = extract_face_encoding(image_bytes)
        except FaceEncoderError as exc:
            raise FaceAuthError(str(exc)) from exc
        user.face_encoding = encoding_to_json(encoding, BIOMETRIC_FACE)

    db.commit()
    db.refresh(user)
    return user


def delete_user(
    db: Session,
    user_id: int,
    *,
    actor_role: str | None,
    actor_user_id: int | None = None,
) -> None:
    _require_admin(actor_role)
    user = get_user_by_id(db, user_id)
    if user is None:
        raise FaceAuthError("User not found.", 404)

    if actor_user_id is not None and user.id == actor_user_id:
        raise FaceAuthError("You cannot delete your own account while signed in.", 400)

    if user.role == ROLE_ADMIN and _admin_count(db) <= 1:
        raise FaceAuthError("Cannot delete the last administrator.", 400)

    db.delete(user)
    db.commit()
