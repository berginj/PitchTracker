"""Pitch type classification using heuristic rules."""

from typing import Dict, List
import numpy as np
from .schemas import PitchClassification


def classify_pitch_heuristic(pitch_data: dict) -> PitchClassification:
    """Classify pitch using MLB-standard heuristic rules.
    
    Args:
        pitch_data: Dict with 'speed_mph', 'run_in', 'rise_in', 'pitch_id'
        
    Returns:
        PitchClassification with type and confidence
    """
    speed = pitch_data.get('speed_mph', 0)
    run = pitch_data.get('run_in', 0)
    rise = pitch_data.get('rise_in', 0)
    pitch_id = pitch_data.get('pitch_id', 'unknown')
    
    # Heuristic classification rules
    confidence = 0.7  # Default medium confidence
    
    if speed >= 88:
        if abs(run) < 3 and abs(rise) < 3:
            pitch_type = "Fastball (4-seam)"
            confidence = 0.85
        elif rise < -2:
            pitch_type = "Sinker"
            confidence = 0.75
        else:
            pitch_type = "Fastball"
            confidence = 0.70
            
    elif 80 <= speed < 88:
        if abs(run) > 4:
            pitch_type = "Slider"
            confidence = 0.80
        elif rise < -3:
            pitch_type = "Changeup"
            confidence = 0.75
        else:
            pitch_type = "Cutter"
            confidence = 0.65
            
    elif 70 <= speed < 80:
        if rise < -4:
            pitch_type = "Curveball"
            confidence = 0.85
        elif rise < -2:
            pitch_type = "Changeup"
            confidence = 0.75
        else:
            pitch_type = "Slider"
            confidence = 0.70
            
    else:  # < 70 mph
        if rise < -5:
            pitch_type = "Curveball (slow)"
            confidence = 0.80
        else:
            pitch_type = "Unknown"
            confidence = 0.30
    
    return PitchClassification(
        pitch_id=pitch_id,
        heuristic_type=pitch_type,
        cluster_id=None,
        confidence=confidence,
        features={
            'speed_mph': speed,
            'run_in': run,
            'rise_in': rise
        }
    )


def classify_pitches(pitches: List[dict]) -> List[PitchClassification]:
    """Classify multiple pitches with k-means clustering.

    Args:
        pitches: List of pitch data dicts

    Returns:
        List of PitchClassification objects with cluster_id assigned
    """
    # First classify with heuristics
    classifications = [classify_pitch_heuristic(p) for p in pitches]

    # If we have enough pitches, run k-means clustering
    if len(pitches) >= 5:
        # Extract features for clustering
        features = []
        valid_indices = []

        for i, p in enumerate(pitches):
            speed = p.get('speed_mph', 0)
            run = p.get('run_in', 0)
            rise = p.get('rise_in', 0)

            if speed > 0:  # Only include pitches with valid speed
                features.append([speed, run, rise])
                valid_indices.append(i)

        if len(features) >= 5:
            # Normalize features
            features_array = np.array(features)
            mean = features_array.mean(axis=0)
            std = features_array.std(axis=0)
            std[std == 0] = 1.0  # Avoid division by zero
            normalized = (features_array - mean) / std

            # Simple k-means clustering (k=3-5 based on pitch count)
            k = min(5, max(3, len(features) // 3))
            from sklearn.cluster import KMeans

            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(normalized)

            # Create new classifications with cluster_id
            new_classifications = []
            cluster_idx = 0

            for i, old_class in enumerate(classifications):
                if i in valid_indices:
                    # Recreate with cluster_id
                    new_class = PitchClassification(
                        pitch_id=old_class.pitch_id,
                        heuristic_type=old_class.heuristic_type,
                        cluster_id=int(cluster_labels[cluster_idx]),
                        confidence=old_class.confidence,
                        features=old_class.features
                    )
                    new_classifications.append(new_class)
                    cluster_idx += 1
                else:
                    # Keep original (no cluster_id)
                    new_classifications.append(old_class)

            return new_classifications

    return classifications
