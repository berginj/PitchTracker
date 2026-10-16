"""One presentation of service-confirmed state and UI command progress."""

from dataclasses import dataclass

from app.services.orchestrator.runtime_status import RuntimeStatus
from ui.coaching.session_commands import SessionOperation
from ui.workspace.contracts import SessionPreparation


@dataclass(frozen=True)
class SessionPresentation:
    label: str
    action: str
    primary: str
    detail: str
    tone: str = "info"
    pending: bool = False


OPERATIONS = {
    "choose_pitcher": "Choosing pitcher", "pitcher": "Changing pitcher", "change_pitcher": "Changing pitcher",
    "prepare_details": "Choosing session details", "confirm_end": "Confirming End Session",
    "prepare": "Preparing cameras", "start_capture": "Preparing cameras",
    "record": "Starting recording", "start_recording": "Starting recording",
    "pause": "Pausing recording", "pause_recording": "Pausing recording",
    "resume": "Resuming recording", "resume_recording": "Resuming recording",
    "end": "Finalizing session", "stop_recording": "Finalizing session",
    "stop_preview": "Stopping preview", "stop_capture": "Stopping preview",
    "shutdown": "Closing cameras and recording workers",
}


def session_presentation(runtime: RuntimeStatus, preparation: SessionPreparation,
                         operation: SessionOperation = SessionOperation()) -> SessionPresentation:
    label, action, primary = "Idle", "prepare", "Prepare Session"
    detail = "Prepare cameras and session details. Recording starts only when you choose Start Recording."
    tone = "info"
    if runtime.capture_phase == "live":
        if preparation.prepared:
            label, action, primary = "Ready", "record", "Start Recording"
            detail = "Cameras are live. Preview is not being recorded. Choose Start Recording when ready."
        else:
            label, primary = "Preview", "Complete Preparation"
            detail = "Cameras are live; recording is off. Complete preparation or stop preview before rig edits."
    elif runtime.capture_phase == "stopping":
        label, action, primary = "Preview stopping", "stop_preview", "Retry Stop Preview"
        detail = "Camera cleanup is incomplete. Retry Stop Preview before preparing another session."
    if runtime.recording_phase == "recording":
        label, action, primary, tone = "Recording", "pause", "Pause", "success"
        detail = "Session recording is active. Pause keeps cameras live; End Session saves accepted work."
    elif runtime.recording_phase == "paused":
        label, action, primary, tone = "Paused", "resume", "Resume Recording", "warning"
        detail = "Recording is paused. Cameras remain live. Resume Recording to record more pitches."
    elif runtime.recording_phase == "finalizing":
        label, action, primary = "Finalizing", "end", "Finalizing…"
        detail = "Accepted analysis and recording artifacts are draining. Review becomes available after completion."
    elif (runtime.recording_phase == "completed" and not preparation.prepared and runtime.finalized_session
          and runtime.capture_phase in {"idle", "live"}):
        label, action, primary = "Completed", "review", "Review Session"
        detail = "Finalization succeeded. Open Sessions to review, or prepare a new session."
    failure_operation = operation.failure_operation or (runtime.failure.operation if runtime.failure else None)
    failure_message = operation.failure_message or (runtime.failure.message if runtime.failure else "")
    pending = operation.pending or runtime.pending_operation
    if pending:
        progress = OPERATIONS.get(pending, pending.replace("_", " ").capitalize())
        primary = progress + "…"
        detail = progress + ". Waiting for service confirmation; navigation remains available."
    elif failure_operation:
        tone = "error"
        retry = {"record": ("record", "Retry Start Recording"), "start_recording": ("record", "Retry Start Recording"),
                 "pause": ("pause", "Retry Pause"), "pause_recording": ("pause", "Retry Pause"),
                 "resume": ("resume", "Retry Resume"), "resume_recording": ("resume", "Retry Resume"),
                 "end": ("end", "Retry End Session"), "stop_recording": ("end", "Retry End Session")}
        retry_supported = (
            failure_operation in {"end", "stop_recording"} and runtime.owns_recording
            or failure_operation in {"pause", "pause_recording"} and runtime.recording_phase == "recording"
            or failure_operation in {"resume", "resume_recording"} and runtime.recording_phase == "paused"
            or failure_operation in {"record", "start_recording"} and preparation.prepared and not runtime.owns_recording)
        if failure_operation in retry and retry_supported:
            action, primary = retry[failure_operation]
        elif runtime.recording_phase == "finalizing":
            action, primary = "end", "Retry End Session"
        if runtime.recording_phase == "finalizing":
            detail = "Finalization is incomplete and the session remains owned. Resolve the issue and retry End Session before review."
        label += " · Error"
        detail = f"{OPERATIONS.get(failure_operation, failure_operation)} failed: {failure_message} " + detail
    elif operation.notice:
        detail = operation.notice + " " + detail
    blocked = bool(pending) or runtime.recording_phase == "finalizing" and not failure_operation
    return SessionPresentation(label, action, primary, detail, tone, blocked)
