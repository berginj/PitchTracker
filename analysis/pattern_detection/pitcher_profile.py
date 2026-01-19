"""Pitcher profile management for baseline comparison."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from analysis.pattern_detection.utils import compute_statistics

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


@dataclass
class ProfileMetrics:
    """Baseline metrics for a pitcher."""

    velocity: Dict[str, float]  # mean, std, min, max, p25, p50, p75
    horizontal_movement: Dict[str, float]  # mean, std, range
    vertical_movement: Dict[str, float]  # mean, std, range
    strike_percentage: float
    consistency_score: float  # 0-1, higher is more consistent


@dataclass
class PitcherProfile:
    """Pitcher baseline profile for comparison."""

    pitcher_id: str
    created_utc: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_updated_utc: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sessions_analyzed: int = 0
    total_pitches: int = 0

    baseline_metrics: Optional[ProfileMetrics] = None
    pitch_repertoire: Dict[str, float] = field(default_factory=dict)  # pitch_type -> percentage
    known_anomalies: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)

        # Convert ProfileMetrics to dict if present
        if self.baseline_metrics:
            result['baseline_metrics'] = asdict(self.baseline_metrics)

        return result

    @classmethod
    def from_dict(cls, data: Dict) -> "PitcherProfile":
        """Create profile from dictionary."""
        # Handle baseline_metrics conversion
        if data.get('baseline_metrics'):
            data['baseline_metrics'] = ProfileMetrics(**data['baseline_metrics'])

        return cls(**data)

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "PitcherProfile":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


class PitcherProfileManager:
    """Manager for pitcher profiles."""

    def __init__(self, profiles_dir: Optional[Path] = None):
        """Initialize profile manager.

        Args:
            profiles_dir: Directory for profile storage (default: configs/pitcher_profiles/)
        """
        if profiles_dir is None:
            profiles_dir = Path("configs/pitcher_profiles")

        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def load_profile(self, pitcher_id: str) -> Optional[PitcherProfile]:
        """Load existing profile or return None.

        Args:
            pitcher_id: Pitcher identifier

        Returns:
            PitcherProfile if exists, None otherwise
        """
        profile_path = self._get_profile_path(pitcher_id)

        if not profile_path.exists():
            return None

        try:
            profile_json = profile_path.read_text()
            return PitcherProfile.from_json(profile_json)
        except Exception as e:
            print(f"Error loading profile for {pitcher_id}: {e}")
            return None

    def save_profile(self, profile: PitcherProfile) -> None:
        """Save profile to disk.

        Args:
            profile: Profile to save
        """
        profile_path = self._get_profile_path(profile.pitcher_id)

        try:
            profile_path.write_text(profile.to_json())
        except Exception as e:
            print(f"Error saving profile for {profile.pitcher_id}: {e}")
            raise

    def create_or_update_profile(
        self,
        pitcher_id: str,
        pitches: List["PitchSummary"]
    ) -> PitcherProfile:
        """Create new profile or update existing with new pitches.

        Args:
            pitcher_id: Pitcher identifier
            pitches: List of pitch summaries to include

        Returns:
            Updated PitcherProfile
        """
        # Load existing or create new
        profile = self.load_profile(pitcher_id)

        if profile is None:
            profile = PitcherProfile(pitcher_id=pitcher_id)

        # Update last modified time
        profile.last_updated_utc = datetime.utcnow().isoformat()

        # Compute baseline metrics
        profile.baseline_metrics = self._compute_baseline_metrics(pitches)

        # Compute pitch repertoire (would need classifications)
        # For now, just count total pitches
        profile.total_pitches = len(pitches)

        # Save and return
        self.save_profile(profile)

        return profile

    def compare_to_baseline(
        self,
        pitcher_id: str,
        current_pitches: List["PitchSummary"]
    ) -> Dict:
        """Compare current session pitches to baseline profile.

        Args:
            pitcher_id: Pitcher identifier
            current_pitches: List of current pitch summaries

        Returns:
            Dictionary with comparison results
        """
        profile = self.load_profile(pitcher_id)

        if profile is None:
            return {"error": "No baseline profile found", "profile_exists": False}

        if profile.baseline_metrics is None:
            return {"error": "Profile exists but has no baseline metrics", "profile_exists": True}

        # Compute current session metrics
        current_metrics = self._compute_baseline_metrics(current_pitches)

        # Compare velocity
        velocity_comparison = self._compare_metric(
            current_metrics.velocity,
            profile.baseline_metrics.velocity,
            "velocity",
            "mph"
        )

        # Compare strike percentage
        strike_comparison = self._compare_strike_percentage(
            current_metrics.strike_percentage,
            profile.baseline_metrics.strike_percentage
        )

        # Compare movement
        h_movement_comparison = self._compare_metric(
            current_metrics.horizontal_movement,
            profile.baseline_metrics.horizontal_movement,
            "horizontal_movement",
            "in"
        )

        v_movement_comparison = self._compare_metric(
            current_metrics.vertical_movement,
            profile.baseline_metrics.vertical_movement,
            "vertical_movement",
            "in"
        )

        return {
            "profile_exists": True,
            "velocity_vs_baseline": velocity_comparison,
            "strike_percentage_vs_baseline": strike_comparison,
            "horizontal_movement_vs_baseline": h_movement_comparison,
            "vertical_movement_vs_baseline": v_movement_comparison
        }

    def _compute_baseline_metrics(
        self,
        pitches: List["PitchSummary"]
    ) -> ProfileMetrics:
        """Compute baseline metrics from pitches.

        Args:
            pitches: List of pitch summaries

        Returns:
            ProfileMetrics with computed statistics
        """
        # Extract velocity data
        velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]
        velocity_stats = compute_statistics(velocities)

        # Extract movement data
        h_movements = [p.run_in for p in pitches if p.run_in is not None]
        v_movements = [p.rise_in for p in pitches if p.rise_in is not None]

        h_movement_stats = compute_statistics(h_movements)
        v_movement_stats = compute_statistics(v_movements)

        # Add range for movement
        h_movement_stats['range'] = [h_movement_stats['min'], h_movement_stats['max']]
        v_movement_stats['range'] = [v_movement_stats['min'], v_movement_stats['max']]

        # Compute strike percentage
        strikes = sum(1 for p in pitches if p.is_strike)
        strike_pct = strikes / len(pitches) if pitches else 0.0

        # Compute consistency score (inverse of coefficient of variation)
        velocity_cv = velocity_stats['std'] / velocity_stats['mean'] if velocity_stats['mean'] > 0 else 1.0
        consistency_score = max(0.0, 1.0 - velocity_cv)

        return ProfileMetrics(
            velocity=velocity_stats,
            horizontal_movement=h_movement_stats,
            vertical_movement=v_movement_stats,
            strike_percentage=strike_pct,
            consistency_score=consistency_score
        )

    def _compare_metric(
        self,
        current: Dict[str, float],
        baseline: Dict[str, float],
        metric_name: str,
        unit: str
    ) -> Dict:
        """Compare current metric to baseline.

        Args:
            current: Current metric statistics
            baseline: Baseline metric statistics
            metric_name: Name of metric
            unit: Unit of measurement

        Returns:
            Comparison dictionary
        """
        current_mean = current['mean']
        baseline_mean = baseline['mean']
        delta = current_mean - baseline_mean

        # Determine status based on delta and std
        baseline_std = baseline['std']
        if abs(delta) < baseline_std:
            status = "normal"
        elif abs(delta) < 2 * baseline_std:
            status = "slightly_above" if delta > 0 else "slightly_below"
        else:
            status = "significantly_above" if delta > 0 else "significantly_below"

        return {
            "current": current_mean,
            "baseline": baseline_mean,
            f"delta_{unit}": delta,
            "status": status,
            "baseline_std": baseline_std
        }

    def _compare_strike_percentage(
        self,
        current: float,
        baseline: float
    ) -> Dict:
        """Compare strike percentage to baseline.

        Args:
            current: Current strike percentage
            baseline: Baseline strike percentage

        Returns:
            Comparison dictionary
        """
        delta = current - baseline

        # Status based on 5% threshold
        if abs(delta) < 0.05:
            status = "normal"
        elif abs(delta) < 0.10:
            status = "slightly_above" if delta > 0 else "slightly_below"
        else:
            status = "significantly_above" if delta > 0 else "significantly_below"

        return {
            "current": current,
            "baseline": baseline,
            "delta": delta,
            "status": status
        }

    def _get_profile_path(self, pitcher_id: str) -> Path:
        """Get file path for pitcher profile.

        Args:
            pitcher_id: Pitcher identifier

        Returns:
            Path to profile JSON file
        """
        # Sanitize pitcher_id for filename
        safe_id = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in pitcher_id)
        return self.profiles_dir / f"{safe_id}.json"

    def list_profiles(self) -> List[str]:
        """List all available pitcher profiles.

        Returns:
            List of pitcher IDs
        """
        profiles = []

        for profile_file in self.profiles_dir.glob("*.json"):
            try:
                profile = PitcherProfile.from_json(profile_file.read_text())
                profiles.append(profile.pitcher_id)
            except Exception:
                continue

        return profiles


__all__ = [
    "ProfileMetrics",
    "PitcherProfile",
    "PitcherProfileManager",
]
