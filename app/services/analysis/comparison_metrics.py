"""Independent opportunity accounting and comparable component-level metrics."""

from dataclasses import asdict
import math
import numpy as np


def distribution(values):
    return {
        "count": len(values),
        "median": float(np.median(values)) if values else None,
        "p95": float(np.percentile(values, 95)) if values else None,
        "max": float(max(values)) if values else None,
    }


def label_identity(opportunity: str | None, target: str | None) -> tuple[str, str] | None:
    if target:
        return ("target", target)
    return ("opportunity", opportunity) if opportunity else None


class ComparisonAudit:
    def __init__(self, session):
        self.labels = {(r["camera_id"], r["frame_index"]): r for r in session["annotation"].get("frames", [])}
        self.opportunities = session["annotation"]["opportunities"]
        self.strata = {}
        self.center_errors = []
        self.target_errors = []
        self.target_ids = set()
        self.reprojection = []
        self.truth = {}
        self.frames = []
        self.associations = []
        self.positive = self.detected = self.false_candidates = self.correct_matches = self.false_matches = 0
        self.unverified_matches = 0
        self.offered = self.labeled = 0
        self.transform = np.asarray(session["transform"]["matrix_4x4"], dtype=float)
        cameras = sorted({f["camera_id"] for f in self.labels.values()})
        groups: dict[tuple[str, str], dict[str, int]] = {}
        for label in self.labels.values():
            identity = label_identity(label.get("opportunity_id"), label.get("target_id"))
            if label["visibility"] == "visible" and identity is not None:
                counts = groups.setdefault(identity, {})
                camera = label["camera_id"]
                counts[camera] = counts.get(camera, 0) + 1
        self.paired_positive = sum(
            min(counts.get(camera, 0) for camera in cameras) for counts in groups.values()
        ) if len(cameras) == 2 else 0

    def frame(self, frame, detections):
        self.offered += 1
        label = self.labels.get((frame.camera_id, frame.frame_index))
        self.frames.append(
            {
                "camera_id": frame.camera_id,
                "frame_index": frame.frame_index,
                "timestamp_ns": frame.t_capture_monotonic_ns,
                "detections": [asdict(d) for d in detections],
            }
        )
        if label is None:
            for d in detections:
                self.truth[d.candidate_id] = (None, None, None, None)
            return
        self.labeled += 1
        if label.get("timestamp_ns") is not None and label["timestamp_ns"] != frame.t_capture_monotonic_ns:
            raise ValueError("Human label timestamp does not match the encoded source frame")
        visibility = label["visibility"]
        if visibility == "occluded":
            self.strata.setdefault(
                label.get("stratum", "occlusion"), {"positive": 0, "detected": 0, "false_candidates": 0, "errors": []}
            )
            for d in detections:
                self.truth[d.candidate_id] = (None, None, None, None)
            return
        closest, distance = None, None
        if visibility == "visible":
            self.positive += 1
            point = np.array(label["center_px"])
            distances = [(float(np.linalg.norm(np.array([d.u, d.v]) - point)), d.candidate_id) for d in detections]
            if distances:
                distance, closest = min(distances)
                tolerance = max(3.0, float(label.get("radius_px", 4.0)) * 2)
                if distance > tolerance:
                    closest = None
            if closest:
                self.detected += 1
                self.center_errors.append(distance)
        self.false_candidates += len(detections) - int(closest is not None)
        stratum = label.get("stratum", "unspecified")
        metric = self.strata.setdefault(stratum, {"positive": 0, "detected": 0, "false_candidates": 0, "errors": []})
        metric["positive"] += int(visibility == "visible")
        metric["detected"] += int(closest is not None)
        metric["false_candidates"] += len(detections) - int(closest is not None)
        if closest:
            metric["errors"].append(distance)
        for d in detections:
            self.truth[d.candidate_id] = (
                d.candidate_id == closest,
                label.get("xyz_ft") if d.candidate_id == closest else None,
                label.get("opportunity_id"),
                label.get("target_id") if d.candidate_id == closest else None,
            )

    def association(self, event):
        self.associations.append(
            {
                "pair_id": event.pair_id,
                "timestamp_ns": event.timestamp_ns,
                "algorithm": event.primary_algorithm,
                "edges": [edge.to_payload() for edge in event.edges],
                "triangulations": [r.to_payload() for r in event.triangulations],
            }
        )
        edges = {edge.edge_id: edge for edge in event.edges}
        for observation in event.triangulations:
            if observation.status != "ACCEPTED" or observation.xyz_ft is None:
                continue
            edge = edges[observation.edge_id]
            left = self.truth.get(edge.left_candidate_id, (None, None, None, None))
            right = self.truth.get(edge.right_candidate_id, (None, None, None, None))
            left_identity, right_identity = label_identity(left[2], left[3]), label_identity(right[2], right[3])
            if left[0] is None or right[0] is None or (left[0] and right[0] and (left_identity is None or right_identity is None)):
                self.unverified_matches += 1
            elif left[0] and right[0] and left_identity is not None and left_identity == right_identity:
                self.correct_matches += 1
                target = left[1] if left[1] is not None else right[1]
                if target is not None:
                    point = (self.transform @ np.r_[observation.xyz_ft, 1.0])[:3]
                    self.target_errors.append(float(np.linalg.norm(point - target)))
                    if left[3] and left[3] == right[3]:
                        self.target_ids.add(left[3])
            else:
                self.false_matches += 1
            self.reprojection.append(float(edge.epipolar_error_px or 0))

    def outcomes(self, attempts):
        outcomes = []
        assigned = set()
        for opportunity in self.opportunities:
            overlapping = []
            for index, attempt in enumerate(attempts):
                start, end = attempt["start_ns"], attempt["end_ns"]
                if end >= opportunity["start_ns"] and start <= opportunity["end_ns"]:
                    overlapping.append(attempt)
                    assigned.add(index)
            if len(overlapping) > 1:
                status = "MULTIPLE_ATTEMPTS"
            elif not overlapping:
                status = "UNAVAILABLE"
            else:
                status = overlapping[0]["status"]
            outcomes.append(
                {
                    "opportunity_id": opportunity["id"],
                    "status": status,
                    "stratum": opportunity.get("stratum", "unspecified"),
                    "attempts": overlapping,
                }
            )
        extras = [attempt for i, attempt in enumerate(attempts) if i not in assigned]
        return outcomes, extras

    def summary(self, attempts):
        outcomes, extras = self.outcomes(attempts)
        return {
            "frames_offered": self.offered,
            "frames_labeled": self.labeled,
            "positive_labels": self.positive,
            "detected_labels": self.detected,
            "false_candidates": self.false_candidates,
            "recall": self.detected / self.positive if self.positive else None,
            "precision": (
                self.detected / (self.detected + self.false_candidates)
                if self.detected + self.false_candidates
                else None
            ),
            "correct_stereo_matches": self.correct_matches,
            "false_stereo_matches": self.false_matches,
            "paired_positive_labels": self.paired_positive,
            "stereo_recall": self.correct_matches / self.paired_positive if self.paired_positive else None,
            "unverified_stereo_matches": self.unverified_matches,
            "center_error_px": distribution(self.center_errors),
            "target_error_ft": distribution(self.target_errors),
            "surveyed_target_ids": sorted(self.target_ids),
            "epipolar_error_px": distribution(self.reprojection),
            "opportunities": len(outcomes),
            "completed_opportunities": sum(r["status"] == "ESTIMATED" for r in outcomes),
            "outcomes": outcomes,
            "extra_attempts": extras,
            "strata": {
                key: {
                    **{k: v for k, v in metric.items() if k != "errors"},
                    "center_error_px": distribution(metric["errors"]),
                }
                for key, metric in self.strata.items()
            },
        }


def summarize_fit(pitch_id, request, result):
    times = [o.t_ns for o in request.observations]
    failures = [code.value for code in result.diagnostics.failure_codes]
    usable = bool(result.samples and result.plate_crossing_xyz_ft is not None and not failures)
    speed = None
    reference = None
    if usable:
        sample = result.samples[0]
        speed = math.sqrt(sample.Vx**2 + sample.Vy**2 + sample.Vz**2) / (22 / 15)
        reference = {
            "source": "vision",
            "reference": "first_observed_point",
            "z_ft": sample.Z,
            "timestamp_ns": sample.t_ns,
        }
    return {
        "pitch_id": pitch_id,
        "start_ns": min(times) if times else 0,
        "end_ns": max(times) if times else 0,
        "status": "ESTIMATED" if usable else "REJECTED",
        "sample_count": len(times),
        "failure_codes": failures,
        "speed_mph": speed,
        "speed_reference": reference,
        "plate_xyz_ft": result.plate_crossing_xyz_ft,
        "plate_timestamp_ns": result.plate_crossing_t_ns,
        "performance": result.diagnostics.performance,
    }
