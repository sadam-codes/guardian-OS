from controllers.activity import router as activity_router
from controllers.face import router as face_router
from controllers.guardian_workflow import router as guardian_router
from controllers.health import router as health_router
from controllers.jarvis import router as jarvis_router
from controllers.vapi import router as vapi_router

__all__ = [
    "activity_router",
    "face_router",
    "guardian_router",
    "health_router",
    "jarvis_router",
    "vapi_router",
]
