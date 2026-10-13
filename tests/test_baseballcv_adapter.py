"""Model compatibility is proved without shipping third-party weights."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from contracts import Detection, Frame
from contracts.model_bundle import ModelBundle, covariance2
from detect.yolo11 import prepare, decode, refine
from app.pipeline.detection.candidate_processing import CandidateProcessor
from configs.settings import load_config
from stereo.calibrated_stereo import CalibratedStereoGeometry, CalibratedStereoMatcher, _fundamental_from_rt
from stereo.global_assignment import evaluate_stereo_assignment


def model_bundle(tmp_path, **updates):
    (tmp_path / "model.onnx").write_bytes(b"test-model-metadata-only")
    data = {
        "schema_version": "detector_bundle.v1",
        "model_file": "model.onnx",
        "model_sha256": hashlib.sha256(b"test-model-metadata-only").hexdigest(),
        "name": "synthetic",
        "class_names": ["baseball"],
        "ball_class_id": 0,
        "source_revision": "synthetic",
        "preprocessing": "rgb_letterbox_114_div255",
        "input_size": [640, 640],
        "licenses": {"code": "unknown", "weights": "synthetic", "data": "synthetic"},
    }
    data.update(updates)
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(data))
    return ModelBundle.load(path)


def test_letterbox_rgb_gray_and_raw_coordinates(tmp_path):
    bundle = model_bundle(tmp_path)
    image = np.zeros((400, 800, 3), np.uint8)
    image[:, :] = [0, 0, 255]
    blob, mapping = prepare(image, bundle.input_size)
    assert blob.shape == (1, 3, 640, 640)
    assert blob[0, 0, 320, 320] == 1 and blob[0, 2, 320, 320] == 0
    frame = Frame("left", 12, 500, image, 800, 400, "BGR8")
    outputs = np.array([[[80], [224], [16], [16], [0.9]]], dtype=np.float32)
    values = decode(outputs, frame, mapping, bundle)
    assert len(values) == 1
    assert values[0].u == pytest.approx(100)
    assert values[0].v == pytest.approx(80)
    assert values[0].radius_basis == "bbox"
    assert values[0].pixel_coordinate_space == "raw"
    gray = np.full((400, 800), 127, np.uint8)
    gray_blob, _ = prepare(gray, bundle.input_size)
    np.testing.assert_array_equal(gray_blob[:, 0], gray_blob[:, 1])


@pytest.mark.parametrize(
    "change",
    [
        {"model_file": "../escape.onnx"},
        {"model_sha256": "0" * 64},
        {"ball_class_id": 3},
        {"output_layout": "guess"},
        {"preprocessing": "bgr_stretch"},
        {"max_candidates": 100},
    ],
)
def test_invalid_bundle_fails_before_inference(tmp_path, change):
    with pytest.raises(ValueError):
        model_bundle(tmp_path, **change)


@pytest.mark.parametrize(
    "covariance", [[[0, 0], [0, 1]], [[1, 2], [2, 1]], [[1, 2], [0, 1]], [[float("nan"), 0], [0, 1]]]
)
def test_bad_covariance_rejected(covariance):
    with pytest.raises(ValueError):
        covariance2(covariance)


def test_output_layout_class_filter_nms_and_nonfinite(tmp_path):
    bundle = model_bundle(tmp_path, class_names=["glove", "baseball"], ball_class_id=1, output_layout="rows")
    frame = Frame("right", 4, 10, np.zeros((640, 640, 3), np.uint8), 640, 640, "BGR8")
    _, transform = prepare(frame.image, bundle.input_size)
    rows = np.array([[100, 100, 10, 10, 0.1, 0.9], [100, 100, 10, 10, 0.1, 0.8], [50, 50, 8, 8, 0.9, 0.1]])
    assert len(decode(rows, frame, transform, bundle)) == 1
    with pytest.raises(ValueError):
        decode(np.zeros((5, 4)), frame, transform, bundle)
    rows[0, 0] = np.nan
    with pytest.raises(ValueError, match="Nonfinite"):
        decode(rows, frame, transform, bundle)


def test_refinement_and_explicit_fallback():
    image = np.zeros((40, 40), np.uint8)
    cv2.circle(image, (19, 20), 3, 255, -1)
    proposal = Detection(
        "left",
        2,
        20,
        20,
        20,
        7,
        0.8,
        bbox_xyxy=(13, 13, 27, 27),
        radius_basis="bbox",
        pixel_covariance_px2=((4.0, 0.0), (0.0, 4.0)),
    )
    refined = refine(image, proposal, ((0.5, 0.0), (0.0, 0.5)))
    assert refined.u == pytest.approx(19)
    assert refined.localization_method == "yolo11_refined"
    failed = refine(np.zeros_like(image), proposal)
    assert failed.localization_method.endswith("failed")
    assert failed.pixel_covariance_px2 == proposal.pixel_covariance_px2


def matcher():
    k = np.array([[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]])
    rotation, translation = np.eye(3), np.array([[-304.8], [0.0], [0.0]])
    geometry = CalibratedStereoGeometry(
        k,
        np.zeros(5),
        k,
        np.zeros(5),
        rotation,
        translation,
        _fundamental_from_rt(k, k, rotation, translation),
        (640, 480),
        3,
        0.1,
        100,
    )
    return CalibratedStereoMatcher(geometry)


def det(camera, x, y=240.0, identity="a", covariance=((0.25, 0.0), (0.0, 0.25))):
    return Detection(camera, 1, 10, x, y, 4, 0.9, candidate_id=camera + identity, pixel_covariance_px2=covariance)


def test_stereo_v3_unique_ambiguous_and_missing_covariance():
    geometry = matcher()
    unique = evaluate_stereo_assignment(
        "p", [det("left", 330)], [det("right", 280)], matcher=geometry, epipolar_tolerance=3, mode="global_v3"
    )
    assert len(unique.primary_matches) == 1
    ambiguous = evaluate_stereo_assignment(
        "p",
        [det("left", 330), det("left", 332, identity="b")],
        [det("right", 280), det("right", 282, identity="b")],
        matcher=geometry,
        epipolar_tolerance=3,
        mode="global_v3",
    )
    assert not ambiguous.primary_matches
    assert any("AMBIGUOUS_ASSIGNMENT" in edge.rejection_reasons for edge in ambiguous.edges)
    missing = evaluate_stereo_assignment(
        "p",
        [det("left", 330, covariance=None)],
        [det("right", 280)],
        matcher=geometry,
        epipolar_tolerance=3,
        mode="global_v3",
    )
    assert missing.edges[0].rejection_reasons == ("PIXEL_COVARIANCE_MISSING",)


def test_localization_covariance_changes_3d_covariance():
    geometry = matcher()
    small = geometry.triangulate(geometry.match(det("left", 330), det("right", 280)))
    large = geometry.triangulate(
        geometry.match(
            det("left", 330, covariance=((4.0, 0.0), (0.0, 4.0))),
            det("right", 280, covariance=((4.0, 0.0), (0.0, 4.0))),
        )
    )
    np.testing.assert_allclose(np.array(large.covariance), np.array(small.covariance) * 16)


def test_shared_candidate_processing_is_causal_and_resets_epoch():
    config = load_config(Path("configs/default.yaml"))
    config = replace(config, stereo=replace(config.stereo, association_mode="global_v3"))
    processor = CandidateProcessor(config)
    image = np.zeros((480, 640), np.uint8)
    frame = Frame("left", 1, 10_000_000, image, 640, 480, "GRAY8", "first")
    first = processor.enrich(
        frame, [replace(det("left", 330), candidate_id="", t_capture_monotonic_ns=frame.t_capture_monotonic_ns)]
    )
    assert not first[0].association_eligible
    following = replace(frame, frame_index=2, t_capture_monotonic_ns=20_000_000)
    second = processor.enrich(
        following,
        [
            replace(
                det("left", 331),
                candidate_id="",
                frame_index=2,
                t_capture_monotonic_ns=following.t_capture_monotonic_ns,
            )
        ],
    )
    assert second[0].association_eligible and second[0].prediction_center_px == (330.0, 240.0)
    restarted = processor.enrich(replace(following, capture_epoch="second"), [replace(second[0], candidate_id="")])
    assert not restarted[0].association_eligible
