"""Anomaly detection for pitch data."""

from typing import List
import numpy as np
from .schemas import Anomaly


def detect_anomalies(pitches: List[dict]) -> List[Anomaly]:
    """Detect anomalies in pitch data using statistical methods.
    
    Args:
        pitches: List of pitch data dicts with speed, movement, trajectory info
        
    Returns:
        List of detected anomalies
    """
    if len(pitches) < 5:
        return []  # Need minimum data for statistical analysis
    
    anomalies = []
    
    # Extract metrics
    speeds = [p.get('speed_mph', 0) for p in pitches if p.get('speed_mph')]
    
    if len(speeds) < 5:
        return anomalies
    
    # Calculate statistics
    speed_mean = np.mean(speeds)
    speed_std = np.std(speeds)
    
    # Detect speed outliers (Z-score > 3)
    for pitch in pitches:
        pitch_id = pitch.get('pitch_id', 'unknown')
        speed = pitch.get('speed_mph')
        
        if not speed:
            continue
            
        z_score = abs(speed - speed_mean) / speed_std if speed_std > 0 else 0
        
        if z_score > 3.0:
            severity = "high" if z_score > 4.0 else "medium"
            direction = "fast" if speed > speed_mean else "slow"
            
            anomalies.append(Anomaly(
                pitch_id=pitch_id,
                anomaly_type="speed_outlier",
                severity=severity,
                details={
                    "speed_mph": speed,
                    "z_score": z_score,
                    "mean_speed": speed_mean,
                    "std_speed": speed_std
                },
                recommendation=f"Unusually {direction} pitch ({speed:.1f} mph vs avg {speed_mean:.1f} mph). "
                              f"Verify radar calibration or pitcher mechanics."
            ))
    
    # Check trajectory quality
    for pitch in pitches:
        pitch_id = pitch.get('pitch_id', 'unknown')
        
        # Check for poor trajectory fit
        rmse = pitch.get('rmse_3d_ft', 0)
        inlier_ratio = pitch.get('inlier_ratio', 1.0)
        sample_count = pitch.get('sample_count', 100)
        
        if rmse > 0.5 or inlier_ratio < 0.7 or sample_count < 10:
            severity = "high" if rmse > 1.0 else "medium"
            
            issues = []
            if rmse > 0.5:
                issues.append(f"high trajectory error ({rmse:.2f} ft)")
            if inlier_ratio < 0.7:
                issues.append(f"low inlier ratio ({inlier_ratio:.2f})")
            if sample_count < 10:
                issues.append(f"insufficient samples ({sample_count})")
            
            anomalies.append(Anomaly(
                pitch_id=pitch_id,
                anomaly_type="trajectory_quality",
                severity=severity,
                details={
                    "rmse_3d_ft": rmse,
                    "inlier_ratio": inlier_ratio,
                    "sample_count": sample_count
                },
                recommendation=f"Poor trajectory quality: {', '.join(issues)}. "
                              f"Check camera alignment and lighting conditions."
            ))
    
    return anomalies
