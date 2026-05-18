import os
import time

from helpers.guardian_events import push_recent_event
from helpers.guardian_memory import get_frequent_commands, record_command
from helpers.guardian_safety import validate_command_safety
from helpers.jarvis import ASSISTANT_NAME, process_jarvis_command
from helpers.jarvis_intent import parse_jarvis_intent
from schemas.guardian_workflow import (
    GuardianWorkflowRequest,
    GuardianWorkflowResponse,
    WorkflowStageLog,
)
from schemas.jarvis import JarvisCommandResponse, JarvisIntent

GESTURE_INTENTS: dict[str, str] = {
    "open_palm": "greet",
    "thumbs_up": "acknowledge",
    "fist": "minimize_all",
    "stop": "volume_mute",
    "swipe_left": "volume_down",
    "swipe_right": "volume_up",
}

PIPELINE_STAGES = [
    "camera_mic_input",
    "identity_verification",
    "voice_understanding",
    "ai_decision_engine",
    "system_action_execution",
    "desktop_control",
]


def _stage(name: str, status: str, detail: str, started: float) -> WorkflowStageLog:
    return WorkflowStageLog(
        stage=name,
        status=status,
        detail=detail,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )


def _gesture_to_text(gesture: str) -> str | None:
    intent = GESTURE_INTENTS.get(gesture)
    if not intent:
        return None
    fallbacks = {
        "greet": "hello",
        "acknowledge": "thanks",
        "minimize_all": "show desktop",
        "volume_mute": "mute",
        "volume_down": "volume down",
        "volume_up": "volume up",
    }
    return fallbacks.get(intent, intent.replace("_", " "))


def execute_guardian_workflow(body: GuardianWorkflowRequest) -> GuardianWorkflowResponse:
    stages: list[WorkflowStageLog] = []
    t0 = time.perf_counter()

    stages.append(
        _stage(
            "camera_mic_input",
            "ok" if body.text or body.gesture else "skip",
            "Voice or gesture input received.",
            t0,
        )
    )

    if not body.identity_verified:
        stages.append(
            _stage(
                "identity_verification",
                "warn",
                "Face not verified in this session — risky commands blocked.",
                t0,
            )
        )
    else:
        stages.append(
            _stage(
                "identity_verification",
                "ok",
                f"Authorized user: {body.user_name or 'verified'}.",
                t0,
            )
        )

    command_text = body.text.strip()
    if body.gesture and not command_text:
        mapped = _gesture_to_text(body.gesture)
        if mapped:
            command_text = mapped
            stages.append(
                _stage(
                    "voice_understanding",
                    "ok",
                    f"Gesture '{body.gesture}' mapped to: {mapped}",
                    t0,
                )
            )
        else:
            stages.append(
                _stage("voice_understanding", "fail", f"Unknown gesture: {body.gesture}", t0)
            )
            return GuardianWorkflowResponse(
                success=False,
                message=f"Unknown gesture: {body.gesture}",
                intent="unknown",
                confidence=0,
                stages=stages,
                security_blocked=False,
            )
    else:
        stages.append(
            _stage("voice_understanding", "ok", f"Command: {command_text[:80]}", t0)
        )

    intent_hint = parse_jarvis_intent(command_text).intent
    if not body.skip_safety:
        safe, reason = validate_command_safety(
            command_text,
            identity_verified=body.identity_verified,
            intent_hint=intent_hint,
        )
        if not safe:
            stages.append(_stage("ai_decision_engine", "blocked", reason or "Blocked", t0))
            push_recent_event(
                {
                    "type": "command_blocked",
                    "user": body.user_name,
                    "detail": reason,
                }
            )
            return GuardianWorkflowResponse(
                success=False,
                message=reason or "Command blocked for safety.",
                intent=intent_hint,
                confidence=0,
                stages=stages,
                security_blocked=True,
            )

    stages.append(_stage("ai_decision_engine", "ok", f"Intent: {intent_hint}", t0))

    jarvis_result: JarvisCommandResponse = process_jarvis_command(
        command_text,
        user_name=body.user_name,
        context=body.context,
    )

    record_command(body.user_id, body.user_name, command_text, jarvis_result.intent)

    exec_status = "ok" if jarvis_result.success else "fail"
    stages.append(
        _stage(
            "system_action_execution",
            exec_status,
            jarvis_result.message,
            t0,
        )
    )
    stages.append(
        _stage(
            "desktop_control",
            exec_status if jarvis_result.action else "skip",
            jarvis_result.action or "No OS action.",
            t0,
        )
    )

    push_recent_event(
        {
            "type": "jarvis_command",
            "user": body.user_name,
            "intent": jarvis_result.intent,
            "success": jarvis_result.success,
            "detail": command_text[:120],
        }
    )

    return GuardianWorkflowResponse(
        success=jarvis_result.success,
        message=jarvis_result.message,
        intent=jarvis_result.intent,
        confidence=jarvis_result.confidence,
        action=jarvis_result.action,
        slots=jarvis_result.slots,
        context=jarvis_result.context,
        stages=stages,
        security_blocked=False,
        jarvis=jarvis_result,
    )


def guardian_status() -> dict:
    from helpers.guardian_memory import memory_entry_count

    os_on = os.getenv("JARVIS_ALLOW_OS", "true").lower() in ("1", "true", "yes")
    return {
        "pipeline": PIPELINE_STAGES,
        "assistant_name": ASSISTANT_NAME,
        "os_control_enabled": os_on,
        "memory_entries": memory_entry_count(),
        "supported_gestures": list(GESTURE_INTENTS.keys()),
    }
