from __future__ import annotations

from pathlib import Path

from contracts.durable_registry import DURABLE_CONTRACTS, validate_durable_contracts
from contracts.setup_capture import SETUP_CAPTURE_SCHEMA_VERSION
from contracts.setup_snapshot import SETUP_SNAPSHOT_SCHEMA


def test_durable_contract_registry_is_self_consistent() -> None:
    root = Path(__file__).resolve().parents[1]

    assert validate_durable_contracts(root) == ()
    assert DURABLE_CONTRACTS["setup_capture"].schema_version == SETUP_CAPTURE_SCHEMA_VERSION
    assert DURABLE_CONTRACTS["setup_snapshot"].schema_version == SETUP_SNAPSHOT_SCHEMA
    assert DURABLE_CONTRACTS["session_summary"].schema_path is not None


def test_durable_contract_registry_has_one_owner_per_artifact() -> None:
    assert len(DURABLE_CONTRACTS) == len({spec.artifact for spec in DURABLE_CONTRACTS.values()})
    assert all(spec.owner for spec in DURABLE_CONTRACTS.values())
