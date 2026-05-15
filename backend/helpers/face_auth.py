import numpy as np
from sqlalchemy.orm import Session

from helpers.face_encoder import (
    FaceEncoderError,
    encoding_from_json,
    encoding_to_json,
    extract_face_encoding,
    face_distance,
    is_match,
)
from helpers.roles import ROLE_ADMIN, ROLE_USER, VALID_ROLES
from models.register import Register


class FaceAuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _find_matching_user(db: Session, encoding: np.ndarray) -> tuple[Register | None, float]:
    best_user: Register | None = None
    best_distance = float("inf")

    for user in db.query(Register).all():
        known = encoding_from_json(user.face_encoding)
        distance = face_distance(known, encoding)
        if distance < best_distance:
            best_distance = distance
            best_user = user

    return best_user, best_distance


def _resolve_signup_role(db: Session, requested_role: str, actor_role: str | None) -> str:
    role = (requested_role or ROLE_USER).strip().lower()
    if role not in VALID_ROLES:
        raise FaceAuthError("Role must be 'admin' or 'user'.")

    user_count = db.query(Register).count()

    if user_count == 0:
        return ROLE_ADMIN

    if role == ROLE_ADMIN and actor_role != ROLE_ADMIN:
        raise FaceAuthError("Only an admin can create admin accounts.", 403)

    return role


def signup_face(
    db: Session,
    name: str,
    image_bytes: bytes,
    role: str = ROLE_USER,
    actor_role: str | None = None,
) -> Register:
    clean_name = name.strip()
    if not clean_name:
        raise FaceAuthError("Name is required.")

    existing = db.query(Register).filter(Register.name == clean_name).first()
    if existing:
        raise FaceAuthError("This name is already registered. Use login or another name.", 409)

    assigned_role = _resolve_signup_role(db, role, actor_role)

    try:
        encoding = extract_face_encoding(image_bytes)
    except FaceEncoderError as exc:
        raise FaceAuthError(str(exc)) from exc

    encoding_vec = np.array(encoding, dtype=np.float64)
    duplicate, distance = _find_matching_user(db, encoding_vec)
    if duplicate is not None and is_match(distance):
        raise FaceAuthError(
            f"This face is already registered as '{duplicate.name}'. Use sign in instead.",
            409,
        )

    user = Register(
        name=clean_name,
        face_encoding=encoding_to_json(encoding),
        role=assigned_role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_face(db: Session, image_bytes: bytes) -> Register:
    try:
        unknown = np.array(extract_face_encoding(image_bytes), dtype=np.float64)
    except FaceEncoderError as exc:
        raise FaceAuthError(str(exc)) from exc

    if not db.query(Register).count():
        raise FaceAuthError("No registered users. Sign up first.", 404)

    best_user, best_distance = _find_matching_user(db, unknown)

    if best_user is None or not is_match(best_distance):
        raise FaceAuthError("Face not recognized. Please sign up first.", 401)

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
        duplicate = (
            db.query(Register)
            .filter(Register.name == clean_name, Register.id != user_id)
            .first()
        )
        if duplicate:
            raise FaceAuthError("This name is already in use.", 409)
        user.name = clean_name

    if role is not None:
        new_role = role.strip().lower()
        if new_role not in VALID_ROLES:
            raise FaceAuthError("Role must be 'admin' or 'user'.")
        if user.role == ROLE_ADMIN and new_role == ROLE_USER and _admin_count(db) <= 1:
            raise FaceAuthError("Cannot remove the last administrator.", 400)
        user.role = new_role

    if name is None and role is None and image_bytes is None:
        raise FaceAuthError("No changes provided.")

    if image_bytes is not None:
        try:
            encoding = extract_face_encoding(image_bytes)
        except FaceEncoderError as exc:
            raise FaceAuthError(str(exc)) from exc

        encoding_vec = np.array(encoding, dtype=np.float64)
        for other in db.query(Register).filter(Register.id != user_id).all():
            known = encoding_from_json(other.face_encoding)
            distance = face_distance(known, encoding_vec)
            if is_match(distance):
                raise FaceAuthError(
                    f"This face is already registered as '{other.name}'.",
                    409,
                )
        user.face_encoding = encoding_to_json(encoding)

    db.commit()
    db.refresh(user)
    return user


def delete_user(
    db: Session,
    user_id: int,
    *,
    actor_role: str | None,
    actor_name: str | None = None,
) -> None:
    _require_admin(actor_role)

    user = get_user_by_id(db, user_id)
    if user is None:
        raise FaceAuthError("User not found.", 404)

    if actor_name and user.name.strip().lower() == actor_name.strip().lower():
        raise FaceAuthError("You cannot delete your own account while signed in.", 400)

    if user.role == ROLE_ADMIN and _admin_count(db) <= 1:
        raise FaceAuthError("Cannot delete the last administrator.", 400)

    db.delete(user)
    db.commit()
