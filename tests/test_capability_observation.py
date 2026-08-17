"""Tests for capability observation contracts and backend integration."""

from __future__ import annotations

from types import MappingProxyType

from contracts.capability_observation import (
    ALL_CONTROLS,
    CONTROL_EXPOSURE,
    CONTROL_FOCUS,
    CONTROL_GAIN,
    CONTROL_WHITE_BALANCE,
    CapabilityObservation,
    ControlQueryResult,
    ControlQueryStatus,
    build_simulated_observation,
)


# -- ControlQueryStatus -------------------------------------------------------


class TestControlQueryStatus:
    def test_is_observed_only_for_supported(self):
        assert ControlQueryStatus.SUPPORTED.is_observed() is True
        assert ControlQueryStatus.UNSUPPORTED.is_observed() is False
        assert ControlQueryStatus.PERMISSION_DENIED.is_observed() is False
        assert ControlQueryStatus.QUERY_FAILED.is_observed() is False
        assert ControlQueryStatus.UNAVAILABLE.is_observed() is False


# -- ControlQueryResult round-trip ---------------------------------------------


class TestControlQueryResultRoundTrip:
    def test_supported_round_trip(self):
        result = ControlQueryResult(
            control=CONTROL_EXPOSURE,
            status=ControlQueryStatus.SUPPORTED,
            observed_value=4000.0,
            requested_value=4000.0,
            backend="uvc",
            reason="readback verified",
            timestamp_utc="2026-01-01T00:00:00Z",
        )
        restored = ControlQueryResult.from_payload(result.to_payload())
        assert restored == result

    def test_query_failed_round_trip(self):
        result = ControlQueryResult(
            control=CONTROL_GAIN,
            status=ControlQueryStatus.QUERY_FAILED,
            backend="opencv",
            reason="DirectShow timeout",
        )
        restored = ControlQueryResult.from_payload(result.to_payload())
        assert restored.status == ControlQueryStatus.QUERY_FAILED
        assert restored.observed_value is None

    def test_permission_denied(self):
        result = ControlQueryResult(
            control=CONTROL_FOCUS,
            status=ControlQueryStatus.PERMISSION_DENIED,
            reason="OS denied access to camera control",
        )
        payload = result.to_payload()
        assert payload["status"] == "permission_denied"

    def test_unavailable_default_from_empty(self):
        result = ControlQueryResult.from_payload({})
        assert result.status == ControlQueryStatus.UNAVAILABLE
        assert result.control == ""


# -- CapabilityObservation round-trip ------------------------------------------


class TestCapabilityObservationRoundTrip:
    def test_full_round_trip(self):
        obs = CapabilityObservation(
            camera_id="SN123",
            backend="uvc",
            results={
                CONTROL_EXPOSURE: ControlQueryResult(
                    control=CONTROL_EXPOSURE,
                    status=ControlQueryStatus.SUPPORTED,
                    observed_value=4000,
                    backend="uvc",
                ),
                CONTROL_FOCUS: ControlQueryResult(
                    control=CONTROL_FOCUS,
                    status=ControlQueryStatus.UNSUPPORTED,
                    backend="uvc",
                    reason="Camera has no autofocus",
                ),
            },
            requested_mode={"width": 1280, "height": 800, "fps": 60},
            negotiated_mode={"width": 1280, "height": 800, "fps": 60},
        )
        restored = CapabilityObservation.from_payload(obs.to_payload())
        assert restored.camera_id == "SN123"
        assert restored.status_for(CONTROL_EXPOSURE) == ControlQueryStatus.SUPPORTED
        assert restored.status_for(CONTROL_FOCUS) == ControlQueryStatus.UNSUPPORTED
        assert restored.observed_value(CONTROL_EXPOSURE) == 4000

    def test_status_for_missing_control(self):
        obs = CapabilityObservation()
        assert obs.status_for("nonexistent") == ControlQueryStatus.UNAVAILABLE
        assert obs.observed_value("nonexistent") is None

    def test_requested_vs_negotiated_distinct(self):
        obs = CapabilityObservation(
            requested_mode={"width": 1920, "fps": 120},
            negotiated_mode={"width": 1280, "fps": 60},
        )
        payload = obs.to_payload()
        assert payload["requested_mode"]["width"] == 1920
        assert payload["negotiated_mode"]["width"] == 1280


# -- Immutable mappings --------------------------------------------------------


class TestImmutableMappings:
    def test_results_is_mapping_proxy(self):
        obs = CapabilityObservation(
            results={
                CONTROL_GAIN: ControlQueryResult(
                    CONTROL_GAIN, ControlQueryStatus.SUPPORTED, 8.0,
                ),
            },
        )
        assert isinstance(obs.results, MappingProxyType)
        assert isinstance(obs.requested_mode, MappingProxyType)
        assert isinstance(obs.negotiated_mode, MappingProxyType)
        assert isinstance(obs.device_metadata, MappingProxyType)

    def test_results_not_mutatable(self):
        obs = CapabilityObservation(results={})
        try:
            obs.results["new"] = "bad"
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_requested_mode_not_mutatable(self):
        obs = CapabilityObservation(requested_mode={"fps": 60})
        try:
            obs.requested_mode["fps"] = 120
            assert False, "Should have raised TypeError"
        except TypeError:
            pass

    def test_source_dict_mutation_does_not_affect_observation(self):
        source = {"width": 640}
        obs = CapabilityObservation(requested_mode=source)
        source["width"] = 9999
        assert obs.requested_mode["width"] == 640

    def test_from_payload_produces_immutable(self):
        payload = CapabilityObservation(
            results={CONTROL_GAIN: ControlQueryResult(CONTROL_GAIN, ControlQueryStatus.SUPPORTED)},
            requested_mode={"w": 1},
        ).to_payload()
        restored = CapabilityObservation.from_payload(payload)
        assert isinstance(restored.results, MappingProxyType)
        assert isinstance(restored.requested_mode, MappingProxyType)

    def test_default_empty_observation_is_immutable(self):
        obs = CapabilityObservation()
        assert isinstance(obs.results, MappingProxyType)
        assert len(obs.results) == 0


# -- Simulated observation ----------------------------------------------------


class TestSimulatedObservation:
    def test_all_controls_present(self):
        obs = build_simulated_observation(
            camera_id="sim-0",
            requested_mode={"width": 640, "height": 480, "fps": 30, "pixfmt": "GRAY8"},
            controls={"exposure": 4000, "gain": 8.0},
        )
        for control in ALL_CONTROLS:
            assert control in obs.results
            assert obs.results[control].status == ControlQueryStatus.SUPPORTED
            assert obs.results[control].backend == "simulated"

    def test_provenance_disclaims_physical_validation(self):
        obs = build_simulated_observation("sim", {}, {})
        assert "does not constitute physical validation" in obs.provenance_note
        for result in obs.results.values():
            assert "Simulated" in result.reason

    def test_round_trip(self):
        obs = build_simulated_observation("sim", {"width": 640}, {})
        restored = CapabilityObservation.from_payload(obs.to_payload())
        assert restored.backend == "simulated"
        assert len(restored.results) == len(ALL_CONTROLS)


# -- SimulatedCamera backend integration ---------------------------------------


class TestSimulatedCameraObservation:
    def test_get_capability_observation(self):
        from capture.simulated_camera import SimulatedCamera

        cam = SimulatedCamera()
        cam.open("sim-test")
        cam.set_mode(640, 480, 30, "GRAY8")
        cam.set_controls(4000, 8.0, None, None)
        obs = cam.get_capability_observation()
        assert obs is not None
        assert obs.backend == "simulated"
        assert obs.status_for(CONTROL_EXPOSURE) == ControlQueryStatus.SUPPORTED
        assert "physical validation" in obs.provenance_note.lower()
        cam.close()

    def test_unopened_simulated_camera_returns_none(self):
        from capture.simulated_camera import SimulatedCamera

        cam = SimulatedCamera()
        assert cam.get_capability_observation() is None


# -- Device/backend/query failure scenarios ------------------------------------


class TestFailureScenarios:
    def test_base_camera_device_returns_none(self):
        from capture.camera_device import CameraDevice

        class StubCamera(CameraDevice):
            def open(self, serial): pass  # noqa: E704
            def set_mode(self, *a, **kw): pass  # noqa: E704
            def set_controls(self, *a, **kw): pass  # noqa: E704
            def read_frame(self, t): raise NotImplementedError  # noqa: E704
            def get_stats(self): raise NotImplementedError  # noqa: E704
            def close(self): pass  # noqa: E704

        assert StubCamera().get_capability_observation() is None

    def test_query_failed_status_serializes(self):
        result = ControlQueryResult(
            control=CONTROL_GAIN,
            status=ControlQueryStatus.QUERY_FAILED,
            reason="Backend raised OSError",
        )
        payload = result.to_payload()
        assert payload["status"] == "query_failed"
        restored = ControlQueryResult.from_payload(payload)
        assert restored.status == ControlQueryStatus.QUERY_FAILED

    def test_permission_denied_status(self):
        result = ControlQueryResult(
            control=CONTROL_EXPOSURE,
            status=ControlQueryStatus.PERMISSION_DENIED,
            reason="Access denied by OS policy",
        )
        assert not result.status.is_observed()
        assert result.to_payload()["status"] == "permission_denied"

    def test_observation_with_mixed_statuses(self):
        obs = CapabilityObservation(
            camera_id="test",
            backend="uvc",
            results={
                CONTROL_EXPOSURE: ControlQueryResult(
                    CONTROL_EXPOSURE, ControlQueryStatus.SUPPORTED, 4000,
                ),
                CONTROL_FOCUS: ControlQueryResult(
                    CONTROL_FOCUS, ControlQueryStatus.PERMISSION_DENIED,
                    reason="OS denied",
                ),
                CONTROL_WHITE_BALANCE: ControlQueryResult(
                    CONTROL_WHITE_BALANCE, ControlQueryStatus.QUERY_FAILED,
                    reason="Timeout",
                ),
            },
        )
        payload = obs.to_payload()
        restored = CapabilityObservation.from_payload(payload)
        assert restored.status_for(CONTROL_EXPOSURE) == ControlQueryStatus.SUPPORTED
        assert restored.status_for(CONTROL_FOCUS) == ControlQueryStatus.PERMISSION_DENIED
        assert restored.status_for(CONTROL_WHITE_BALANCE) == ControlQueryStatus.QUERY_FAILED
        assert restored.status_for(CONTROL_GAIN) == ControlQueryStatus.UNAVAILABLE


# -- UVC observation builder ---------------------------------------------------


class TestUvcObservationBuilder:
    def test_focus_supported_when_write_and_readback_verified(self):
        from capture.uvc_capability_observation import build_uvc_observation

        obs = build_uvc_observation(
            serial="SN1", requested_width=1280, requested_height=800,
            requested_fps=60, requested_pixfmt="GRAY8",
            mode={"width": 1280, "height": 800, "fps": 60.0, "pixfmt": "GRAY8"},
            controls={
                "autofocus_disable_write_succeeded": True,
                "autofocus_disabled": True,
                "autofocus_readback_raw": 0.0,
                "exposure_readback_us": 4000.0,
                "exposure_us": 4000,
                "gain_readback": 8.0,
                "gain": 8.0,
            },
        )
        assert obs.status_for(CONTROL_FOCUS) == ControlQueryStatus.SUPPORTED

    def test_focus_query_failed_when_write_ok_but_readback_mismatch(self):
        from capture.uvc_capability_observation import build_uvc_observation

        obs = build_uvc_observation(
            serial="SN1", requested_width=1280, requested_height=800,
            requested_fps=60, requested_pixfmt="GRAY8",
            mode={"width": 1280, "height": 800, "fps": 60.0, "pixfmt": "GRAY8"},
            controls={
                "autofocus_disable_write_succeeded": True,
                "autofocus_disabled": False,
                "autofocus_readback_raw": 1.0,
            },
        )
        assert obs.status_for(CONTROL_FOCUS) == ControlQueryStatus.QUERY_FAILED

    def test_focus_query_failed_when_write_did_not_succeed(self):
        from capture.uvc_capability_observation import build_uvc_observation

        obs = build_uvc_observation(
            serial="SN1", requested_width=1280, requested_height=800,
            requested_fps=60, requested_pixfmt="GRAY8",
            mode={"width": 1280, "height": 800, "fps": 60.0, "pixfmt": "GRAY8"},
            controls={"autofocus_disable_write_succeeded": False},
        )
        assert obs.status_for(CONTROL_FOCUS) == ControlQueryStatus.QUERY_FAILED

    def test_focus_unavailable_when_never_attempted(self):
        from capture.uvc_capability_observation import build_uvc_observation

        obs = build_uvc_observation(
            serial="SN1", requested_width=1280, requested_height=800,
            requested_fps=60, requested_pixfmt="GRAY8",
            mode={"width": 1280, "height": 800, "fps": 60.0, "pixfmt": "GRAY8"},
            controls={},
        )
        assert obs.status_for(CONTROL_FOCUS) == ControlQueryStatus.UNAVAILABLE

    def test_readback_none_is_query_failed_not_unavailable(self):
        from capture.uvc_capability_observation import _readback_result

        result = _readback_result(
            CONTROL_GAIN, None, 8.0, "uvc", "2026-01-01T00:00:00Z",
            attempted=True,
        )
        assert result.status == ControlQueryStatus.QUERY_FAILED

    def test_readback_not_attempted_is_unavailable(self):
        from capture.uvc_capability_observation import _readback_result

        result = _readback_result(
            CONTROL_GAIN, None, 8.0, "uvc", "2026-01-01T00:00:00Z",
            attempted=False,
        )
        assert result.status == ControlQueryStatus.UNAVAILABLE

    def test_wb_grayscale_is_unavailable(self):
        from capture.uvc_capability_observation import build_uvc_observation

        obs = build_uvc_observation(
            serial="SN1", requested_width=1280, requested_height=800,
            requested_fps=60, requested_pixfmt="GRAY8",
            mode={"width": 1280, "height": 800, "fps": 60.0, "pixfmt": "GRAY8"},
            controls={"color_white_balance_verified": None},
        )
        assert obs.status_for(CONTROL_WHITE_BALANCE) == ControlQueryStatus.UNAVAILABLE

    def test_wb_verified_false_is_query_failed(self):
        from capture.uvc_capability_observation import build_uvc_observation

        obs = build_uvc_observation(
            serial="SN1", requested_width=1280, requested_height=800,
            requested_fps=60, requested_pixfmt="YUYV",
            mode={"width": 1280, "height": 800, "fps": 60.0, "pixfmt": "YUY2"},
            controls={"color_white_balance_verified": False, "wb_readback": 5000.0},
        )
        assert obs.status_for(CONTROL_WHITE_BALANCE) == ControlQueryStatus.QUERY_FAILED


# -- Focus capability semantics in camera_capabilities -------------------------


class TestFocusCapabilitySemantics:
    def test_supported_focus_means_autofocus_true(self):
        from calib.camera_capabilities import CameraCapabilityDetector

        detector = CameraCapabilityDetector()
        obs = CapabilityObservation(results={
            CONTROL_FOCUS: ControlQueryResult(
                CONTROL_FOCUS, ControlQueryStatus.SUPPORTED, 0.0,
            ),
        })

        class FakeCam:
            def get_capability_observation(self):
                return obs

            def read_frame(self, t):
                return None

        assert detector._query_uvc_autofocus(FakeCam()) is True

    def test_unsupported_focus_means_autofocus_false(self):
        from calib.camera_capabilities import CameraCapabilityDetector

        detector = CameraCapabilityDetector()
        obs = CapabilityObservation(results={
            CONTROL_FOCUS: ControlQueryResult(
                CONTROL_FOCUS, ControlQueryStatus.UNSUPPORTED,
            ),
        })

        class FakeCam:
            def get_capability_observation(self):
                return obs

        assert detector._query_uvc_autofocus(FakeCam()) is False

    def test_query_failed_focus_means_unknown(self):
        from calib.camera_capabilities import CameraCapabilityDetector

        detector = CameraCapabilityDetector()
        obs = CapabilityObservation(results={
            CONTROL_FOCUS: ControlQueryResult(
                CONTROL_FOCUS, ControlQueryStatus.QUERY_FAILED,
            ),
        })

        class FakeCam:
            def get_capability_observation(self):
                return obs

        assert detector._query_uvc_autofocus(FakeCam()) is None

    def test_no_observation_means_unknown(self):
        from calib.camera_capabilities import CameraCapabilityDetector

        detector = CameraCapabilityDetector()

        class FakeCam:
            def get_capability_observation(self):
                return None

        assert detector._query_uvc_autofocus(FakeCam()) is None


# -- Recommendation determinism ------------------------------------------------


class TestRecommendationDeterminism:
    def test_same_inputs_produce_same_recommendations(self):
        from calib.camera_capabilities import CameraCapabilityDetector

        detector = CameraCapabilityDetector()
        for _ in range(3):
            recs = detector._generate_recommendations(
                camera_type="industrial",
                has_autofocus=False,
                stability_score=95.0,
                warmup_stable=True,
            )
            assert recs == detector._generate_recommendations(
                camera_type="industrial",
                has_autofocus=False,
                stability_score=95.0,
                warmup_stable=True,
            )


# -- Backend file guard --------------------------------------------------------


class TestBackendFileGuard:
    def test_uvc_backend_does_not_exceed_head_line_count(self):
        from pathlib import Path

        uvc_path = Path(__file__).parent.parent / "capture" / "uvc_backend.py"
        line_count = len(uvc_path.read_text(encoding="utf-8").splitlines())
        # HEAD at review/production-readiness was 558 lines (grandfathered).
        # New observation code is extracted to uvc_capability_observation.py.
        assert line_count <= 558, (
            f"capture/uvc_backend.py is {line_count} lines; "
            f"must stay <= 558 (HEAD count). Extract to helpers."
        )
