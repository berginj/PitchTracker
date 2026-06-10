"""Saved alignment presets and preset comparison.

Persistence helpers for capturing a known-good alignment as a named preset and
comparing the current alignment against it.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from analysis.camera_alignment_types import AlignmentResults


def save_alignment_preset(results: AlignmentResults, preset_name: str,
                          left_serial: str, right_serial: str) -> None:
    """Save current alignment as a preset/profile.

    Args:
        results: Alignment results to save
        preset_name: Name for this preset (e.g., "baseline_2026-01-20")
        left_serial: Left camera serial
        right_serial: Right camera serial
    """
    import json
    from datetime import datetime

    presets_dir = Path("alignment_checks/presets")
    presets_dir.mkdir(parents=True, exist_ok=True)

    preset_data = {
        "preset_name": preset_name,
        "saved_at": datetime.now().isoformat(),
        "left_camera": left_serial,
        "right_camera": right_serial,
        "quality_score": results.get_quality_score(),
        "quality_rating": results.quality,
        "metrics": {
            "focal_diff_percent": results.scale_difference_percent,
            "scale_ratio": results.scale_ratio,
            "toin_std_px": results.convergence_std_px,
            "correlation": results.correlation,
            "vertical_mean_px": results.vertical_mean_px,
            "vertical_max_px": results.vertical_max_px,
            "rotation_deg": results.rotation_deg,
            "num_matches": results.num_matches
        },
        "status": {
            "focal": results.scale_status,
            "horizontal": results.horizontal_status,
            "vertical": results.vertical_status,
            "rotation": results.rotation_status
        }
    }

    # Save to file
    preset_file = presets_dir / f"{preset_name}.json"
    preset_file.write_text(json.dumps(preset_data, indent=2))


def load_alignment_preset(preset_name: str) -> Optional[dict]:
    """Load a saved alignment preset.

    Args:
        preset_name: Name of preset to load

    Returns:
        Preset data dict or None if not found
    """
    import json

    preset_file = Path("alignment_checks/presets") / f"{preset_name}.json"
    if not preset_file.exists():
        return None

    try:
        return json.loads(preset_file.read_text())
    except Exception:
        return None


def list_alignment_presets() -> List[dict]:
    """List all saved alignment presets.

    Returns:
        List of preset metadata dicts
    """
    import json

    presets_dir = Path("alignment_checks/presets")
    if not presets_dir.exists():
        return []

    presets = []
    for preset_file in presets_dir.glob("*.json"):
        try:
            data = json.loads(preset_file.read_text())
            presets.append({
                "name": preset_file.stem,
                "saved_at": data.get("saved_at", "Unknown"),
                "quality_score": data.get("quality_score", 0),
                "quality_rating": data.get("quality_rating", "UNKNOWN")
            })
        except Exception:
            continue

    # Sort by saved date (newest first)
    presets.sort(key=lambda x: x["saved_at"], reverse=True)
    return presets


def compare_with_preset(current: AlignmentResults, preset_data: dict) -> dict:
    """Compare current alignment with a saved preset.

    Args:
        current: Current alignment results
        preset_data: Loaded preset data

    Returns:
        Dict with comparison details
    """
    preset_metrics = preset_data["metrics"]

    # Calculate deltas
    focal_delta = current.scale_difference_percent - preset_metrics["focal_diff_percent"]
    toin_delta = current.convergence_std_px - preset_metrics["toin_std_px"]
    vertical_delta = current.vertical_mean_px - preset_metrics["vertical_mean_px"]
    rotation_delta = current.rotation_deg - preset_metrics["rotation_deg"]

    # Calculate score delta
    current_score = current.get_quality_score()
    preset_score = preset_data["quality_score"]
    score_delta = current_score - preset_score

    # Determine overall trend
    if score_delta > 5:
        trend = "BETTER"
        trend_emoji = "📈"
    elif score_delta < -5:
        trend = "WORSE"
        trend_emoji = "📉"
    else:
        trend = "SIMILAR"
        trend_emoji = "➡️"

    return {
        "preset_name": preset_data["preset_name"],
        "preset_date": preset_data["saved_at"][:10],
        "current_score": current_score,
        "preset_score": preset_score,
        "score_delta": score_delta,
        "trend": trend,
        "trend_emoji": trend_emoji,
        "deltas": {
            "focal": {
                "current": current.scale_difference_percent,
                "preset": preset_metrics["focal_diff_percent"],
                "delta": focal_delta,
                "better": abs(focal_delta) < 0 or (abs(current.scale_difference_percent) < abs(preset_metrics["focal_diff_percent"]))
            },
            "toin": {
                "current": current.convergence_std_px,
                "preset": preset_metrics["toin_std_px"],
                "delta": toin_delta,
                "better": toin_delta < 0
            },
            "vertical": {
                "current": current.vertical_mean_px,
                "preset": preset_metrics["vertical_mean_px"],
                "delta": vertical_delta,
                "better": abs(vertical_delta) < 0 or (abs(current.vertical_mean_px) < abs(preset_metrics["vertical_mean_px"]))
            },
            "rotation": {
                "current": current.rotation_deg,
                "preset": preset_metrics["rotation_deg"],
                "delta": rotation_delta,
                "better": abs(rotation_delta) < 0 or (abs(current.rotation_deg) < abs(preset_metrics["rotation_deg"]))
            }
        }
    }
