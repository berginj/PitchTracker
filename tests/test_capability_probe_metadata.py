from __future__ import annotations

from contracts.capability_observation import (
    CONTROL_EXPOSURE,
    CapabilityObservation,
    ControlQueryResult,
    ControlQueryStatus,
    build_unavailable_observation,
)


def test_probe_metadata_round_trip() -> None:
    observation = CapabilityObservation(
        camera_id="camera-1",
        results={
            CONTROL_EXPOSURE: ControlQueryResult(
                CONTROL_EXPOSURE,
                ControlQueryStatus.SUPPORTED,
                query_method="directshow_iam_camera_control",
                error_code="",
            )
        },
        supported_modes=({"width": 1280, "height": 800, "fps_max": 60},),
        probe_version="uvc-probe-v1",
        device_metadata={"driver_version": "1.2.3"},
    )

    restored = CapabilityObservation.from_payload(observation.to_payload())

    assert restored.results[CONTROL_EXPOSURE].query_method == "directshow_iam_camera_control"
    assert restored.supported_modes[0]["fps_max"] == 60
    assert restored.probe_version == "uvc-probe-v1"
    assert restored.device_metadata["driver_version"] == "1.2.3"


def test_legacy_payload_defaults_new_probe_fields() -> None:
    restored = CapabilityObservation.from_payload(
        {"camera_id": "legacy", "results": {}, "requested_mode": {}}
    )

    assert restored.supported_modes == ()
    assert restored.probe_version == ""
    assert dict(restored.device_metadata) == {}


def test_unavailable_observation_defines_every_control() -> None:
    observation = build_unavailable_observation(
        "camera-1",
        "uvc",
        "probe missing",
    )

    assert observation.results
    assert all(
        result.status == ControlQueryStatus.UNAVAILABLE
        for result in observation.results.values()
    )
    assert all(result.reason == "probe missing" for result in observation.results.values())
