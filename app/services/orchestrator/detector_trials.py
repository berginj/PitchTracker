"""Orchestrator-owned wiring for an operator's bounded shadow detector trial."""

from typing import Any, Callable, Type
from app.services.analysis.detector_trial import DetectorTrial


class DetectorTrialMethods:
    _detector_trial: DetectorTrial | None

    def __getattr__(self, name: str) -> Any:
        raise AttributeError(name)

    def subscribe_event(self, event_type: Type, handler: Callable) -> None:
        """Register a public EventBus subscription."""
        self._event_bus.subscribe(event_type, handler)

    def unsubscribe_event(self, event_type: Type, handler: Callable) -> bool:
        """Remove a public EventBus subscription."""
        return bool(self._event_bus.unsubscribe(event_type, handler))

    def _check_experimental_config_edit(self, config):
        profiles = (self._config, config)
        experimental = any(
            c and (c.detector.model_format == "yolo_v11" or c.stereo.association_mode == "global_v3") for c in profiles
        )
        if self._capturing and experimental and self._config != config:
            raise ValueError("Edit experimental profiles through rig setup while idle")

    def start_detector_trial(self, bundle_path, variant, output, cancel=None):
        if not self._capturing or not self._recording_active or self._recording_paused or self._config is None:
            raise RuntimeError("Start a recording session before requesting a detector trial")
        if self._detector_trial is not None:
            raise RuntimeError("A detector trial is already running")
        directory = self.get_session_dir()
        if directory is None:
            raise RuntimeError("Recording session artifacts are unavailable")
        trial = DetectorTrial(
            self._event_bus,
            self._config,
            bundle_path,
            variant,
            output,
            lambda: self._recording_active and not self._recording_paused,
            directory,
            self._backend,
            self._runtime_calibration_path,
            self._runtime_roi_path,
            self._left_serial,
            self._right_serial,
            self._active_rig_profile.field_transform,
            cancel,
        )
        self._detector_trial = trial
        try:
            trial.start()
        except Exception:
            self._detector_trial = None
            raise

    def stop_detector_trial(self):
        trial, self._detector_trial = self._detector_trial, None
        return trial.stop() if trial is not None else None
