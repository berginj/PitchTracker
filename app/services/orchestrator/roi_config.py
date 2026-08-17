"""Runtime ROI loading and application for the pipeline orchestrator.

Loads lane and plate ROI maps from the active rig profile and applies them
to the detection service. Extracted from PipelineOrchestrator to keep that
file under 500 lines.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, TYPE_CHECKING, Tuple

from configs.roi_io import load_runtime_roi_maps
from log_config.logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from app.services.detection import DetectionServiceImpl


def apply_runtime_rois(
    detection_service: DetectionServiceImpl,
    runtime_roi_path: Optional[Path],
    left_serial: str,
    right_serial: str,
) -> None:
    """Load ROIs from disk and apply them to the detection service.

    Args:
        detection_service: DetectionServiceImpl (untyped to avoid circular import)
        runtime_roi_path: Path to the rig-profile ROI directory
        left_serial: Left camera serial or label
        right_serial: Right camera serial or label
    """
    if detection_service is None or runtime_roi_path is None:
        return

    lane_by_serial, plate_by_serial = load_runtime_roi_maps(
        runtime_roi_path,
        left_serial,
        right_serial,
        lane_path=Path("rois/shared_lane_rois.json"),
    )
    lane_rois = _serial_roi_map_to_camera_ids(
        lane_by_serial, left_serial, right_serial
    )
    plate_rois = _serial_roi_map_to_camera_ids(
        plate_by_serial, left_serial, right_serial
    )
    if not lane_rois and not plate_rois:
        logger.warning(f"No runtime ROIs loaded from {runtime_roi_path}")
        return
    detection_service.set_lane_rois(lane_rois, plate_rois or None)
    logger.info(
        f"Runtime ROIs loaded from {runtime_roi_path} "
        f"(lane={sorted(lane_rois.keys())}, plate={sorted(plate_rois.keys())})"
    )


def _serial_roi_map_to_camera_ids(
    roi_map: Mapping[str, Sequence[Tuple[int | float, int | float]]],
    left_serial: str,
    right_serial: str,
) -> Dict[str, List[Tuple[float, float]]]:
    """Map ROIs keyed by 'left'/'right' or serial to camera-id keys."""
    left = roi_map.get("left") or roi_map.get(left_serial)
    right = roi_map.get("right") or roi_map.get(right_serial)
    output: Dict[str, List[Tuple[float, float]]] = {}
    if left is not None:
        output[left_serial] = [(float(x), float(y)) for x, y in left]
    if right is not None:
        output[right_serial] = [(float(x), float(y)) for x, y in right]
    return output
