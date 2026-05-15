from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from config.database import get_db
from helpers.face_auth import (
    FaceAuthError,
    delete_user,
    get_user_by_id,
    list_registered_users,
    login_face,
    signup_face,
    update_user,
)
from helpers.roles import ROLE_USER
from schemas.face import (
    FaceLoginResponse,
    FaceSignupResponse,
    RegisteredUserItem,
    RegisteredUsersResponse,
    UserDeleteResponse,
    UserUpdateResponse,
)

router = APIRouter(prefix="/face", tags=["face"])


async def _read_image(image: UploadFile) -> bytes:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload a valid image file (JPG/PNG).")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Image file is empty.")
    return data


@router.post("/signup", response_model=FaceSignupResponse)
async def face_signup(
    name: str = Form(..., min_length=1, max_length=100),
    image: UploadFile = File(...),
    role: str = Form(default=ROLE_USER),
    actor_role: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> FaceSignupResponse:
    image_bytes = await _read_image(image)
    try:
        user = signup_face(db, name, image_bytes, role=role, actor_role=actor_role)
    except FaceAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    role_label = "Administrator" if user.role == "admin" else "User"
    return FaceSignupResponse(
        message=f"{user.name} enrolled successfully as {role_label}.",
        name=user.name,
        id=user.id,
        role=user.role,
    )


@router.post("/login", response_model=FaceLoginResponse)
async def face_login(
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> FaceLoginResponse:
    image_bytes = await _read_image(image)
    try:
        user = login_face(db, image_bytes)
    except FaceAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    role_label = "Administrator" if user.role == "admin" else "User"
    return FaceLoginResponse(
        message=f"Welcome back, {user.name}! ({role_label})",
        name=user.name,
        id=user.id,
        role=user.role,
    )


@router.get("/users/{user_id}", response_model=RegisteredUserItem)
def get_user(
    user_id: int,
    actor_role: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RegisteredUserItem:
    if actor_role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return RegisteredUserItem(id=user.id, name=user.name, role=user.role, created_at=user.created_at)


@router.put("/users/{user_id}", response_model=UserUpdateResponse)
async def update_registered_user(
    user_id: int,
    actor_role: str = Form(...),
    name: str | None = Form(default=None),
    role: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> UserUpdateResponse:
    image_bytes = None
    if image and image.filename:
        image_bytes = await _read_image(image)

    try:
        user = update_user(
            db,
            user_id,
            actor_role=actor_role,
            name=name,
            role=role,
            image_bytes=image_bytes,
        )
    except FaceAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    item = RegisteredUserItem(id=user.id, name=user.name, role=user.role, created_at=user.created_at)
    return UserUpdateResponse(message=f"Updated {user.name} successfully.", user=item)


@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
def remove_registered_user(
    user_id: int,
    actor_role: str,
    actor_name: str | None = None,
    db: Session = Depends(get_db),
) -> UserDeleteResponse:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    display_name = user.name
    try:
        delete_user(db, user_id, actor_role=actor_role, actor_name=actor_name)
    except FaceAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return UserDeleteResponse(message=f"Deleted {display_name} successfully.")


@router.get("/users", response_model=RegisteredUsersResponse)
def get_registered_users(db: Session = Depends(get_db)) -> RegisteredUsersResponse:
    users = list_registered_users(db)
    return RegisteredUsersResponse(
        count=len(users),
        users=[
            RegisteredUserItem(id=u.id, name=u.name, role=u.role, created_at=u.created_at)
            for u in users
        ],
    )
