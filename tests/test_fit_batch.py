"""Immutable source evidence, cache resume, cancellation and replay mapping."""

from dataclasses import replace
import csv
import json
from threading import Event

import numpy as np
import pytest

from app.events.trajectory_events import TrajectoryFitPreparedEvent
from app.pipeline.recording.evidence_journal import SessionEvidenceJournal
from app.pipeline.recording.frame_timestamps import TIMESTAMP_COLUMNS, timestamp_row
from app.services.analysis.batch_inputs import digest
from app.services.analysis.fit_batch import run_fit_batch
from app.services.analysis.research_priority import set_capture_active
from app.services.analysis.video_replay import video_frames
from contracts import Frame
from contracts.fit_jobs import FitBatchRequest
from trajectory.contracts import TrajectoryFitRequest
from trajectory.serialization import encode_request
from trajectory.sim import SimConfig, simulate_ballistic


def recorded_session(path):
    path.mkdir()
    request = TrajectoryFitRequest(
        simulate_ballistic(SimConfig(outlier_prob=0, noise_ft=0.01)), 0, correlation_id="pitch-1"
    )
    request = replace(
        request,
        observations=[
            replace(obs, covariance=((0.0004, 0, 0), (0, 0.0004, 0), (0, 0, 0.0004))) for obs in request.observations
        ],
    )
    journal = SessionEvidenceJournal(path)
    journal.submit_event(TrajectoryFitPreparedEvent("pitch-1", json.loads(encode_request(request))))
    journal.close()
    return request


def test_batch_preserves_sources_and_reuses_exact_inputs(tmp_path):
    source = tmp_path / "session"
    original = recorded_session(source)
    hashes = {path: digest(path) for path in source.rglob("*") if path.is_file()}
    request = FitBatchRequest((source,), tmp_path / "derived", workers=1)
    progress = []
    first = run_fit_batch(request, progress=progress.append).report
    second = run_fit_batch(replace(request, job_id="resume")).report
    assert first["completed"] == 1 and not first["blockers"]
    assert not first["results"][0]["reused"]
    assert second["results"][0]["reused"]
    artifact = json.loads(open(first["results"][0]["artifact"], encoding="utf-8").read())
    assert artifact["request"]["payload"]["observations"][0]["covariance"] == [
        list(row) for row in original.observations[0].covariance
    ]
    assert artifact["physical_claim_eligible"] is False
    assert all(digest(path) == value for path, value in hashes.items())
    assert len(hashes) == len([path for path in source.rglob("*") if path.is_file()])
    changed = run_fit_batch(replace(request, overrides={"drag_sigma": 0.001})).report
    assert changed["results"][0]["cache_key"] != first["results"][0]["cache_key"]
    assert progress[-1].status == "completed"


def test_batch_reports_incomplete_source_without_fitting(tmp_path):
    source = tmp_path / "session"
    recorded_session(source)
    manifest = source / "evidence_journal" / "manifest.json"
    value = json.loads(manifest.read_text())
    value["complete"] = False
    manifest.write_text(json.dumps(value))
    report = run_fit_batch(FitBatchRequest((source,), tmp_path / "output", workers=1)).report
    assert report["completed"] == 0
    assert "incomplete" in report["blockers"][0]["reason"]


def test_pause_cancel_produces_resumable_report(tmp_path):
    source = tmp_path / "session"
    recorded_session(source)
    cancel = Event()
    owner = object()
    set_capture_active(owner, True)
    statuses = []

    def progress(value):
        statuses.append(value.status)
        if value.status == "paused_for_capture":
            cancel.set()

    try:
        report = run_fit_batch(FitBatchRequest((source,), tmp_path / "output", workers=1), cancel, progress).report
    finally:
        set_capture_active(owner, False)
    assert report["status"] == "cancelled" and report["completed"] == 0
    assert "paused_for_capture" in statuses


def test_reject_source_overlap_and_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="separate"):
        FitBatchRequest((tmp_path,), tmp_path / "derived")
    with pytest.raises(ValueError, match="identifier"):
        FitBatchRequest((tmp_path / "source",), tmp_path / "output", job_id="../other")


def test_video_mapping_preserves_camera_frame_indices_and_failures(tmp_path, monkeypatch):
    class Decoder:
        def __init__(self, path):
            self.frames = iter([np.zeros((8, 10, 3), dtype=np.uint8)] * 2)
            self.closed = False

        def isOpened(self):
            return True

        def read(self):
            value = next(self.frames, None)
            return value is not None, value

        def release(self):
            self.closed = True

    decoder = Decoder(None)
    monkeypatch.setattr("app.services.analysis.video_replay.cv2.VideoCapture", lambda path: decoder)
    csv_path = tmp_path / "timestamps.csv"
    frame = Frame("camera-serial", 15, 100, None, 10, 8, "BGR8", "epoch")
    with csv_path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(TIMESTAMP_COLUMNS)
        writer.writerow(timestamp_row(frame, 0, "accepted"))
        writer.writerow(timestamp_row(replace(frame, frame_index=16, t_capture_monotonic_ns=200), None, "failed"))
        writer.writerow(timestamp_row(replace(frame, frame_index=17, t_capture_monotonic_ns=300), 1, "accepted"))
    frames = list(video_frames(tmp_path / "video.avi", csv_path, lambda: None))
    assert [frame.frame_index for frame in frames] == [15, 17]
    assert decoder.closed


def test_video_replay_blocks_ambiguous_legacy_mapping(tmp_path, monkeypatch):
    class Decoder:
        def isOpened(self):
            return True

        def release(self):
            pass

    monkeypatch.setattr("app.services.analysis.video_replay.cv2.VideoCapture", lambda path: Decoder())
    csv_path = tmp_path / "timestamps.csv"
    csv_path.write_text("camera_id,frame_index,t_capture_monotonic_ns\nleft,0,10\n")
    with pytest.raises(ValueError, match="ambiguous"):
        list(video_frames(tmp_path / "video.avi", csv_path, lambda: None))
