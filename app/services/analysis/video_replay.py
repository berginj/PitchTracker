"""Deterministic stereo video replay using runtime detection and pitch state."""

from dataclasses import replace
import csv
import heapq
import json
from pathlib import Path
from uuid import uuid4
from typing import Any, Generator

import cv2
import numpy as np

from app.pipeline.detection.processor import DetectionProcessor
from app.pipeline.initialization import PipelineInitializer
from app.pipeline.pitch_snapshot import PitchConfig, PitchData
from app.pipeline.pitch_tracking_v2 import PitchStateMachineV2
from app.services.analysis.batch_inputs import digest
from calib.field_transform import FieldTransform
from configs.settings import load_config
from contracts import Frame
from contracts.timing import TimestampEvidence
from trajectory.camera_model import load_stereo_ray_camera_models
from trajectory.contracts import TrajectoryFitRequest


def video_frames(video: Path, timestamps: Path, check, accounting=None) -> Generator[Frame, None, None]:
    """Decode every explicitly mapped frame; ambiguous legacy mappings fail closed."""
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError(f"Cannot open recorded video: {video}")
        encoded, last_time, epoch = 0, -1, None
        with timestamps.open(newline="", encoding="utf-8") as source:
            rows = csv.DictReader(source)
            if not {"encoded_frame_index", "write_status"}.issubset(rows.fieldnames or []):
                raise ValueError("Legacy video has no explicit encoded frame mapping; replay is ambiguous")
            for row in rows:
                check()
                if accounting is not None:
                    accounting["offered"] = accounting.get("offered", 0) + 1
                if row["write_status"] == "failed":
                    if accounting is not None:
                        accounting["failed_writes"] = accounting.get("failed_writes", 0) + 1
                    if row["encoded_frame_index"]:
                        raise ValueError("Failed frame has an encoded index")
                    continue
                if row["write_status"] != "accepted" or int(row["encoded_frame_index"]) != encoded:
                    raise ValueError("Video frame mapping is incomplete or not contiguous")
                success, image = capture.read()
                if not success:
                    raise ValueError("Video ended before its timestamp mapping")
                timestamp = int(row["t_capture_monotonic_ns"])
                if timestamp <= last_time or (epoch is not None and row["capture_epoch"] != epoch):
                    raise ValueError("Video timestamps are not increasing within one capture epoch")
                last_time, epoch = timestamp, row["capture_epoch"]
                encoded += 1
                yield Frame(
                    row["camera_id"],
                    int(row["frame_index"]),
                    timestamp,
                    image,
                    image.shape[1],
                    image.shape[0],
                    "BGR8",
                    epoch,
                    timing=TimestampEvidence.from_payload(json.loads(row["timestamp_evidence"])),
                )
        if capture.read()[0]:
            raise ValueError("Video contains frames without timestamp mappings")
    finally:
        capture.release()


def replay(session, batch, check, accounting=None):
    paths = (batch.config_path, batch.calibration_path, batch.roi_path, batch.field_transform_path)
    if any(path is None or not path.is_file() for path in paths):
        raise ValueError("Replay input files are missing")
    config = load_config(batch.config_path)
    with np.load(batch.calibration_path, allow_pickle=False) as calibration:
        if "production_ready" not in calibration or not bool(calibration["production_ready"]):
            raise ValueError("Replay requires a full, production-ready stereo calibration")
    transform = FieldTransform(**json.loads(batch.field_transform_path.read_text(encoding="utf-8")))
    if not transform.passes_residual_gate:
        raise ValueError("Replay field transform fails its residual gate")
    matrix = np.asarray(transform.matrix_4x4)
    models = {
        key: model.in_transformed_world_frame(matrix)
        for key, model in load_stereo_ray_camera_models(batch.calibration_path).items()
    }
    provenance: dict[str, Any] = {
        "basis": "video_reprocessed",
        "inputs": {str(path.resolve()): digest(path) for path in paths},
        "frames_processed": 0,
        "pairing_outcomes": {},
        "source_mapping": {"left": {}, "right": {}},
        "rejected_pitches": [],
    }
    if accounting is not None:
        accounting.update(provenance)
        provenance = accounting
    streams = []
    for label in ("left", "right"):
        video = session / f"session_{label}.avi"
        timestamps = session / f"session_{label}_timestamps.csv"
        provenance["inputs"].update(
            {str(video.resolve()): digest(video), str(timestamps.resolve()): digest(timestamps)}
        )
        streams.append(video_frames(video, timestamps, check, provenance["source_mapping"][label]))
    try:
        first = [next(stream, None) for stream in streams]
        if any(frame is None for frame in first):
            raise ValueError("Both recorded cameras must contain mapped frames")
        frames = [frame for frame in first if frame is not None]
        ids = [frame.camera_id for frame in frames]
        initializer = PipelineInitializer()
        initializer.initialize_detector_config(config)
        polygon, lane, stereo_gate, plate, plate_stereo = initializer.load_rois(
            ids[0],
            ids[1],
            batch.roi_path,
            batch.roi_path,
        )
        if lane is None or plate is None:
            raise ValueError("Replay requires lane and plate ROIs for the recorded camera identifiers")
        # Give each detector its own camera's lane polygon.
        from configs.roi_io import load_runtime_roi_maps

        lane_maps, _ = load_runtime_roi_maps(batch.roi_path, *ids)
        detectors = {}
        for label, camera_id in zip(("left", "right"), ids):
            points = lane_maps.get(camera_id)
            polygon = [(float(x), float(y)) for x, y in points] if points else None
            detectors[label] = initializer.build_detectors(ids[0], ids[1], polygon)[label]
        processor = DetectionProcessor(
            config,
            initializer.create_stereo_matcher(config, batch.calibration_path),
            lane,
            plate,
            stereo_gate,
            plate_stereo,
            lambda: config.ball.radius_in[config.ball.type],
        )
        state = PitchStateMachineV2(
            PitchConfig(
                min_active_frames=config.recording.session_min_active_frames,
                end_gap_frames=config.recording.session_end_gap_frames,
                pre_roll_ms=0,
                frame_rate=float(config.camera.fps),
            )
        )
        pitches: list[PitchData] = []
        state.set_callbacks(
            on_pitch_end=pitches.append,
            on_pitch_rejected=lambda pitch, reason: provenance["rejected_pitches"].append(
                {
                    "pitch_index": pitch.pitch_index,
                    "reason": reason,
                    "sample_count": len(pitch.observations),
                    "start_ns": pitch.start_ns,
                    "end_ns": pitch.end_ns,
                }
            ),
        )

        def paired(left, right, left_dets, right_dets, observations, lane_count, plate_count):
            for obs in observations:
                xyz = transform.apply((obs.X, obs.Y, obs.Z))
                covariance = (
                    None if obs.covariance is None else matrix[:3, :3] @ np.asarray(obs.covariance) @ matrix[:3, :3].T
                )
                state.add_observation(replace(obs, X=xyz[0], Y=xyz[1], Z=xyz[2], covariance=covariance))
            state.update(
                max(left.t_capture_monotonic_ns, right.t_capture_monotonic_ns),
                lane_count,
                plate_count,
                len(observations),
            )

        def rays(label, frame, observations, lane_count, plate_count):
            for obs in observations:
                state.add_ray_observation(obs)

        def pairing(outcome):
            key = str(outcome.status)
            counts = provenance["pairing_outcomes"]
            counts[key] = counts.get(key, 0) + 1

        processor.set_stereo_pair_callback(paired)
        processor.set_ray_observation_callback(rays)
        # Pairing diagnostics are carried with the derived job, never the source.
        processor.set_pairing_outcome_callback(pairing)
        heap = [(frame.t_capture_monotonic_ns, index, frame) for index, frame in enumerate(frames)]
        heapq.heapify(heap)
        last_ns = 0
        while heap:
            check()
            timestamp, index, frame = heapq.heappop(heap)
            if (frame.width, frame.height) != (config.camera.width, config.camera.height):
                raise ValueError("Recorded image dimensions do not match the replay configuration")
            label = ("left", "right")[index]
            processor.process_detection_result(label, frame, detectors[label].detect(frame))
            provenance["frames_processed"] += 1
            last_ns = timestamp
            following = next(streams[index], None)
            if following is not None:
                heapq.heappush(heap, (following.t_capture_monotonic_ns, index, following))
        processor.flush_pairing_buffers("OFFLINE_EOF")
        state.force_end(last_ns)
        if any(digest(Path(path)) != value for path, value in provenance["inputs"].items()):
            raise ValueError("Replay input changed while processing")
        modes = list(dict.fromkeys([config.trajectory.primary_mode, *config.trajectory.compare_modes]))
        for pitch in pitches:
            for mode in modes:
                yield f"replay_{pitch.pitch_index:05d}", TrajectoryFitRequest(
                    pitch.observations,
                    config.metrics.plate_plane_z_ft,
                    ray_observations=pitch.ray_observations,
                    camera_models=models,
                    mode=mode,
                    drag_k0=config.metrics.drag_k0_default,
                    drag_sigma=config.trajectory.drag_sigma,
                    drag_prior_enabled=config.trajectory.drag_prior_enabled,
                    observation_sigma_ft=config.trajectory.observation_sigma_ft,
                    max_speed_std_mph=config.trajectory.max_speed_std_mph,
                    correlation_id=uuid4().hex,
                ), provenance
    finally:
        for stream in streams:
            stream.close()
