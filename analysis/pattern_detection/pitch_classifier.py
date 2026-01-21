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
    """Classify multiple pitches.
    
    Args:
        pitches: List of pitch data dicts
        
    Returns:
        List of PitchClassification objects
    """
    return [classify_pitch_heuristic(p) for p in pitches]
