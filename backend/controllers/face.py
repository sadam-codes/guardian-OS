from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from config.database import get_db
from helpers.activity_log import STATUS_FAILURE, STATUS_SUCCESS, record_activity
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
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload a valid image file (JPG/PNG).")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Image file is empty.")
    return data


async def _collect_image_bytes(
    image: UploadFile | None,
    images: list[UploadFile] | None,
) -> list[bytes]:
    uploads: list[UploadFile] = []
    if image and image.filename:
        uploads.append(image)
    for item in images or []:
        if item.filename:
            uploads.append(item)
    if not uploads:
        raise HTTPException(status_code=400, detail="Upload at least one camera frame.")
    return [await _read_image(item) for item in uploads]


@router.post("/signup", response_model=FaceSignupResponse)
async def face_signup(
    name: str = Form(..., min_length=1, max_length=100),
    image: UploadFile | None = File(default=None),
    images: list[UploadFile] = File(default=[]),
    role: str = Form(default=ROLE_USER),
    actor_role: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> FaceSignupResponse:
    image_bytes_list = await _collect_image_bytes(image, images)
    actor = actor_role if actor_role == "admin" else None
    try:
        user = signup_face(
            db, name, image_bytes_list=image_bytes_list, role=role, actor_role=actor_role
        )
    except FaceAuthError as exc:
        record_activity(
            db,
            event_type="signup",
            status=STATUS_FAILURE,
            message=exc.message,
            actor_name=actor,
            target_name=name.strip(),
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    role_label = "Administrator" if user.role == "admin" else "User"
    record_activity(
        db,
        event_type="signup",
        status=STATUS_SUCCESS,
        message=f"{user.name} enrolled as {role_label}",
        actor_name=actor,
        target_name=user.name,
    )
    return FaceSignupResponse(
        message=f"{user.name} enrolled with face scan as {role_label}.",
        name=user.name,
        id=user.id,
        role=user.role,
    )


@router.post("/login", response_model=FaceLoginResponse)
async def face_login(
    image: UploadFile | None = File(default=None),
    images: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
) -> FaceLoginResponse:
    image_bytes_list = await _collect_image_bytes(image, images)
    try:
        user = login_face(db, image_bytes_list=image_bytes_list)
    except FaceAuthError as exc:
        record_activity(
            db,
            event_type="login",
            status=STATUS_FAILURE,
            message=exc.message,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    role_label = "Administrator" if user.role == "admin" else "User"
    record_activity(
        db,
        event_type="login",
        status=STATUS_SUCCESS,
        message=f"{user.name} signed in ({role_label})",
        actor_name=user.name,
    )
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
    actor_name: str | None = Form(default=None),
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
        record_activity(
            db,
            event_type="user_update",
            status=STATUS_FAILURE,
            message=exc.message,
            actor_name=actor_name,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    record_activity(
        db,
        event_type="user_update",
        status=STATUS_SUCCESS,
        message=f"Updated user {user.name}",
        actor_name=actor_name,
        target_name=user.name,
    )
    item = RegisteredUserItem(id=user.id, name=user.name, role=user.role, created_at=user.created_at)
    return UserUpdateResponse(message=f"Updated {user.name} successfully.", user=item)


@router.delete("/users/{user_id}", response_model=UserDeleteResponse)
def remove_registered_user(
    user_id: int,
    actor_role: str,
    actor_user_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> UserDeleteResponse:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    display_name = user.name
    try:
        delete_user(db, user_id, actor_role=actor_role, actor_user_id=actor_user_id)
    except FaceAuthError as exc:
        record_activity(
            db,
            event_type="user_delete",
            status=STATUS_FAILURE,
            message=exc.message,
            target_name=display_name,
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    record_activity(
        db,
        event_type="user_delete",
        status=STATUS_SUCCESS,
        message=f"Deleted user {display_name}",
        target_name=display_name,
    )
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
