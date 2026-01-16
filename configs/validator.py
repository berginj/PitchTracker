"""Configuration validation using JSON Schema."""

from __future__ import annotations

from typing import Any, Dict

import jsonschema
from jsonschema import Draft7Validator, validators

from exceptions import ConfigValidationError
from log_config.logger import get_logger

logger = get_logger(__name__)

# JSON Schema for default.yaml configuration
CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["camera", "stereo", "detector", "metrics"],
    "properties": {
        "camera": {
            "type": "object",
            "required": ["width", "height", "fps"],
            "properties": {
                "width": {"type": "integer", "minimum": 640, "maximum": 3840},
                "height": {"type": "integer", "minimum": 480, "maximum": 2160},
                "fps": {"type": "integer", "minimum": 30, "maximum": 120},
                "pixfmt": {"type": "string", "enum": ["GRAY8", "RGB24", "YUYV"]},
                "exposure_us": {"type": "integer", "minimum": 100, "maximum": 33000},
                "gain": {"type": "number", "minimum": 0.0, "maximum": 30.0},
                "wb_mode": {"type": ["string", "null"]},
                "wb": {"type": ["array", "null"]},
                "queue_depth": {"type": "integer", "minimum": 1, "maximum": 30},
            },
        },
        "stereo": {
            "type": "object",
            "required": ["baseline_ft", "focal_length_px"],
            "properties": {
                "pairing_tolerance_ms": {"type": "number", "minimum": 0.1, "maximum": 100},
                "epipolar_epsilon_px": {"type": "number", "minimum": 0.5, "maximum": 50},
                "baseline_ft": {"type": "number", "minimum": 0.1, "maximum": 10.0},
                "focal_length_px": {"type": "number", "minimum": 100, "maximum": 5000},
                "cx": {"type": ["number", "null"]},
                "cy": {"type": ["number", "null"]},
                "z_min_ft": {"type": "number", "minimum": 1, "maximum": 20},
                "z_max_ft": {"type": "number", "minimum": 20, "maximum": 200},
                "max_jump_in": {"type": "number", "minimum": 1, "maximum": 100},
            },
        },
        "tracking": {
            "type": "object",
            "properties": {
                "gate_distance_ft": {"type": "number", "minimum": 0.1, "maximum": 5.0},
                "min_track_frames": {"type": "integer", "minimum": 2, "maximum": 100},
            },
        },
        "metrics": {
            "type": "object",
            "required": ["plate_plane_z_ft"],
            "properties": {
                "coordinate_system": {"type": "string"},
                "plate_plane_z_ft": {"type": "number"},
                "release_plane_z_ft": {"type": "number"},
                "approach_window_ft": {"type": "number", "minimum": 1, "maximum": 20},
                "velo_bounds_mph": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "hb_bounds_in": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "ivb_bounds_in": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "release_height_bounds_ft": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
            },
        },
        "recording": {
            "type": "object",
            "properties": {
                "pre_roll_ms": {"type": "integer", "minimum": 0, "maximum": 5000},
                "post_roll_ms": {"type": "integer", "minimum": 0, "maximum": 5000},
                "output_dir": {"type": "string"},
                "session_min_active_frames": {"type": "integer", "minimum": 1},
                "session_end_gap_frames": {"type": "integer", "minimum": 1},
            },
        },
        "ui": {
            "type": "object",
            "properties": {
                "refresh_hz": {"type": "number", "minimum": 1, "maximum": 60},
            },
        },
        "telemetry": {
            "type": "object",
            "properties": {
                "latency_p95_ms_warn": {"type": "number", "minimum": 10, "maximum": 5000},
            },
        },
        "detector": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"type": "string", "enum": ["classical", "ml"]},
                "model_path": {"type": ["string", "null"]},
                "model_input_size": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 128, "maximum": 1024},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "model_conf_threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "model_class_id": {"type": "integer", "minimum": 0},
                "model_format": {"type": "string", "enum": ["yolo_v5", "yolo_v8"]},
                "mode": {"type": "string", "enum": ["MODE_A", "MODE_B"]},
                "frame_diff_threshold": {"type": "number", "minimum": 0, "maximum": 255},
                "bg_diff_threshold": {"type": "number", "minimum": 0, "maximum": 255},
                "bg_alpha": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "edge_threshold": {"type": "number", "minimum": 0, "maximum": 255},
                "blob_threshold": {"type": "number", "minimum": 0, "maximum": 255},
                "runtime_budget_ms": {"type": "number", "minimum": 0.1, "maximum": 100},
                "crop_padding_px": {"type": "integer", "minimum": 0, "maximum": 200},
                "min_consecutive": {"type": "integer", "minimum": 1, "maximum": 10},
                "filters": {
                    "type": "object",
                    "properties": {
                        "min_area": {"type": ["integer", "null"], "minimum": 1},
                        "max_area": {"type": ["integer", "null"], "minimum": 1},
                        "min_circularity": {"type": ["number", "null"], "minimum": 0.0, "maximum": 1.0},
                        "max_circularity": {"type": ["number", "null"], "minimum": 0.0, "maximum": 1.0},
                        "min_velocity": {"type": ["number", "null"], "minimum": 0.0},
                        "max_velocity": {"type": ["number", "null"], "minimum": 0.0},
                    },
                },
            },
        },
        "strike_zone": {
            "type": "object",
            "properties": {
                "batter_height_in": {"type": "number", "minimum": 40, "maximum": 96},
                "top_ratio": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "bottom_ratio": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "plate_width_in": {"type": "number", "minimum": 10, "maximum": 30},
                "plate_length_in": {"type": "number", "minimum": 10, "maximum": 30},
            },
        },
        "ball": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["baseball", "softball"]},
                "radius_in": {
                    "type": "object",
                    "properties": {
                        "baseball": {"type": "number", "minimum": 1.0, "maximum": 2.0},
                        "softball": {"type": "number", "minimum": 1.5, "maximum": 2.5},
                    },
                },
            },
        },
    },
}


def extend_with_default(validator_class):
    """Extend JSON Schema validator to set default values."""
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for prop, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(prop, subschema["default"])

        for error in validate_properties(validator, properties, instance, schema):
            yield error

    return validators.extend(validator_class, {"properties": set_defaults})


DefaultValidatingValidator = extend_with_default(Draft7Validator)


def validate_config(config: Dict[str, Any]) -> None:
    """Validate configuration against JSON Schema.

    Args:
        config: Configuration dictionary

    Raises:
        ConfigValidationError: If configuration is invalid
    """
    try:
        validator = DefaultValidatingValidator(CONFIG_SCHEMA)
        errors = list(validator.iter_errors(config))

        if errors:
            error_messages = []
            for error in errors:
                path = " -> ".join(str(p) for p in error.path) if error.path else "root"
                error_messages.append(f"{path}: {error.message}")

            logger.error(f"Configuration validation failed with {len(errors)} errors")
            for msg in error_messages:
                logger.error(f"  - {msg}")

            raise ConfigValidationError(
                f"Configuration validation failed with {len(errors)} error(s). See logs for details.",
                validation_errors=error_messages,
            )

        logger.info("Configuration validation passed")

    except jsonschema.exceptions.SchemaError as e:
        logger.error(f"Invalid schema: {e}")
        raise ConfigValidationError(f"Invalid schema definition: {e}")


def validate_config_file(config_path: str) -> None:
    """Validate a YAML configuration file.

    Args:
        config_path: Path to configuration file

    Raises:
        ConfigValidationError: If configuration is invalid
    """
    import yaml
    from pathlib import Path

    path = Path(config_path)
    if not path.exists():
        raise ConfigValidationError(f"Configuration file not found: {config_path}")

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML: {e}")
        raise ConfigValidationError(f"Failed to parse configuration file: {e}")

    validate_config(config)


__all__ = ["validate_config", "validate_config_file", "CONFIG_SCHEMA"]
