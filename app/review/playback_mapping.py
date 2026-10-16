"""Conservative encoded-frame mapping for recorded pitch navigation."""

from bisect import bisect_left
import csv
from dataclasses import dataclass
from pathlib import Path

from app.review.session_artifacts import LoadedSession


@dataclass(frozen=True)
class PitchPlayback:
    pitch_id: str
    frame_index: int | None
    reason: str = ""


def read_timestamps(path: Path, frame_count: int) -> tuple[int, ...]:
    times: list[int] = []
    epoch = None
    with path.open(newline="", encoding="utf-8") as source:
        rows = csv.DictReader(source)
        required = {"encoded_frame_index", "write_status", "t_capture_monotonic_ns", "capture_epoch"}
        if not required.issubset(rows.fieldnames or []):
            raise ValueError("Legacy video has no verified encoded-frame mapping")
        for row in rows:
            if row["write_status"] == "failed" and not row["encoded_frame_index"]:
                continue
            if row["write_status"] != "accepted" or int(row["encoded_frame_index"]) != len(times):
                raise ValueError("Video frame mapping is incomplete or not contiguous")
            timestamp = int(row["t_capture_monotonic_ns"])
            if timestamp < 0 or (times and timestamp <= times[-1]):
                raise ValueError("Video timestamps are not strictly increasing")
            if not row["capture_epoch"] or (epoch is not None and row["capture_epoch"] != epoch):
                raise ValueError("Video mapping has missing or mixed capture epochs")
            epoch = row["capture_epoch"]
            times.append(timestamp)
    if not times or len(times) != frame_count:
        raise ValueError("Video frame count does not match its timestamp mapping")
    return tuple(times)


def pitch_playback(session: LoadedSession, left_count: int, right_count: int) -> tuple[PitchPlayback, ...]:
    try:
        if left_count != right_count:
            raise ValueError("Paired pitch playback is unavailable for unequal camera frame counts")
        left = read_timestamps(session.left_timestamps_path, left_count)
        right = read_timestamps(session.right_timestamps_path, right_count)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return tuple(PitchPlayback(p.pitch_id, None, str(exc)) for p in session.pitches)
    results = []
    for pitch in session.pitches:
        try:
            start, end = pitch.manifest.get("t_start_ns"), pitch.manifest.get("t_end_ns")
            if type(start) is not int or type(end) is not int or end < start:
                raise ValueError("Pitch timestamps are missing or invalid")
            if any(start < times[0] or end > times[-1] for times in (left, right)):
                raise ValueError("Pitch lies outside the recorded video timestamp range")
            lidx, ridx = bisect_left(left, start), bisect_left(right, start)
            if lidx != ridx or left[lidx] > end or right[ridx] > end:
                raise ValueError("Paired pitch playback is unavailable for unequal camera frame mappings")
            results.append(PitchPlayback(pitch.pitch_id, lidx))
        except (ValueError, IndexError) as exc:
            results.append(PitchPlayback(pitch.pitch_id, None, str(exc)))
    return tuple(results)
