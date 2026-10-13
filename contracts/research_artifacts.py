"""Shared metadata for local research artifacts, never physical approvals."""

from datetime import datetime, timezone
from contracts.versioning import APP_VERSION


def research_metadata(schema_version):
    return {
        "schema_version": schema_version,
        "app_version": APP_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "physical_claim_eligible": False,
    }
