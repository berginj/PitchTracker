"""Tests for the camera catalog contracts and service."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.catalog import CameraCatalogService, CatalogError, default_catalog_entries
from contracts.catalog import (
    SIDE_LEFT,
    SIDE_RIGHT,
    CameraCapabilities,
    CameraCatalogEntry,
    CameraMode,
    KnownDevice,
    KnownGoodSettings,
)

# -- Contract round-trips ----------------------------------------------------


def test_camera_mode_round_trip():
    mode = CameraMode(1280, 800, 60)
    assert CameraMode.from_payload(mode.to_payload()) == mode


def test_capabilities_best_mode_and_supports():
    caps = CameraCapabilities.from_detected_modes(
        [(640, 480, 30), (1280, 800, 60)], controls=["exposure"], global_shutter=True
    )
    assert caps.best_mode() == CameraMode(1280, 800, 60)
    assert caps.supports(640, 480, 30) is True
    assert caps.supports(1920, 1080, 30) is False
    assert caps.global_shutter is True


def test_capabilities_best_mode_empty():
    assert CameraCapabilities().best_mode() is None


def test_catalog_entry_round_trip():
    entry = CameraCatalogEntry(
        model="ArduCam OV9281",
        vendor="ArduCam",
        capabilities=CameraCapabilities.from_detected_modes([(1280, 800, 60)]),
        known_good=KnownGoodSettings(exposure_us=4000.0, gain=8.0, white_balance_k=4600.0, working_distance_in=120.0),
        global_shutter=True,
        match_names=("arducam", "ov9281"),
    )
    restored = CameraCatalogEntry.from_payload(entry.to_payload())
    assert restored == entry
    assert restored.matches_name("ArduCam B0497 (OV9281)") is True
    assert restored.matches_name("Logitech BRIO") is False


def test_known_device_round_trip():
    dev = KnownDevice(hardware_id="SN1", model="m", friendly_name="f", side=SIDE_LEFT, last_seen_utc="t")
    assert KnownDevice.from_payload(dev.to_payload()) == dev


# -- Service -----------------------------------------------------------------


@pytest.fixture
def catalog_path(tmp_path: Path) -> Path:
    return tmp_path / "camera_catalog.json"


def test_service_seeds_defaults_when_absent(catalog_path):
    svc = CameraCatalogService(catalog_path=catalog_path)
    entries = svc.entries()
    assert len(entries) == len(default_catalog_entries())
    assert any(e.global_shutter for e in entries)


def test_service_no_seed_when_disabled(catalog_path):
    svc = CameraCatalogService(catalog_path=catalog_path, seed_defaults=False)
    assert svc.entries() == []


def test_match_model_by_friendly_name(catalog_path):
    svc = CameraCatalogService(catalog_path=catalog_path)
    match = svc.match_model("ArduCam B0497 (OV9281) USB Camera")
    assert match is not None
    assert "ArduCam" in match.model
    assert svc.match_model("Random Webcam") is None


def test_save_and_reload_round_trips(catalog_path):
    svc = CameraCatalogService(catalog_path=catalog_path)
    svc.remember_device("SN1", friendly_name="ArduCam OV9281", side=SIDE_LEFT)
    svc.save()

    reloaded = CameraCatalogService(catalog_path=catalog_path)
    reloaded.load()
    assert reloaded.get_device("SN1") is not None
    assert reloaded.get_device("SN1").side == SIDE_LEFT
    assert len(reloaded.entries()) >= 1


def test_remember_device_matches_model_and_carries_over(catalog_path):
    svc = CameraCatalogService(catalog_path=catalog_path)
    dev = svc.remember_device("SN1", friendly_name="ArduCam Global Shutter")
    assert dev.model != ""  # matched a catalog model
    # Re-remembering without a side preserves the prior side.
    svc.assign_side("SN1", SIDE_RIGHT)
    again = svc.remember_device("SN1", friendly_name="ArduCam Global Shutter")
    assert again.side == SIDE_RIGHT
    assert again.last_seen_utc != ""


def test_known_good_for_recognised_device(catalog_path):
    svc = CameraCatalogService(catalog_path=catalog_path)
    svc.remember_device("SN1", friendly_name="ArduCam Global Shutter")
    kg = svc.known_good_for("SN1")
    assert kg is not None
    assert kg.exposure_us > 0
    # Unknown device -> no known-good.
    assert svc.known_good_for("UNKNOWN") is None


def test_remember_device_requires_hardware_id(catalog_path):
    svc = CameraCatalogService(catalog_path=catalog_path)
    with pytest.raises(CatalogError):
        svc.remember_device("")


def test_add_entry_overwrite_semantics(catalog_path):
    svc = CameraCatalogService(catalog_path=catalog_path, seed_defaults=False)
    entry = CameraCatalogEntry(model="X", match_names=("x",))
    assert svc.add_entry(entry) is True
    # Same model, no overwrite -> rejected.
    assert svc.add_entry(CameraCatalogEntry(model="X"), overwrite=False) is False
    assert svc.add_entry(CameraCatalogEntry(model="X", vendor="new"), overwrite=True) is True
    assert svc.get_entry("X").vendor == "new"


def test_publish_excludes_devices_and_pull_merges(tmp_path):
    src = CameraCatalogService(catalog_path=tmp_path / "src.json")
    src.remember_device("SN1", friendly_name="ArduCam Global Shutter", side=SIDE_LEFT)
    src.add_entry(CameraCatalogEntry(model="Custom Cam", vendor="Acme", match_names=("acme",)))
    published = src.publish(tmp_path / "published.json")

    import json

    payload = json.loads(published.read_text(encoding="utf-8"))
    assert "devices" not in payload  # local device state must not be published
    assert any(e["model"] == "Custom Cam" for e in payload["entries"])

    dest = CameraCatalogService(catalog_path=tmp_path / "dest.json", seed_defaults=False)
    merged = dest.pull(published)
    assert merged == len(payload["entries"])
    assert dest.get_entry("Custom Cam") is not None


def test_pull_overwrite_flag(tmp_path):
    a = CameraCatalogService(catalog_path=tmp_path / "a.json", seed_defaults=False)
    a.add_entry(CameraCatalogEntry(model="Cam", vendor="original", match_names=("cam",)))
    pub = a.publish(tmp_path / "pub.json")

    b = CameraCatalogService(catalog_path=tmp_path / "b.json", seed_defaults=False)
    b.add_entry(CameraCatalogEntry(model="Cam", vendor="local", match_names=("cam",)))
    # Without overwrite the local entry stays.
    assert b.pull(pub, overwrite=False) == 0
    assert b.get_entry("Cam").vendor == "local"
    # With overwrite the incoming entry wins.
    assert b.pull(pub, overwrite=True) == 1
    assert b.get_entry("Cam").vendor == "original"


def test_pull_bad_file_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    svc = CameraCatalogService(catalog_path=tmp_path / "c.json", seed_defaults=False)
    with pytest.raises(CatalogError):
        svc.pull(bad)
