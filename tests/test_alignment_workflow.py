"""Integration tests for camera alignment workflow."""

import pytest
import numpy as np
from pathlib import Path

from analysis.camera_alignment import (
    analyze_alignment,
    AlignmentResults,
    save_alignment_preset,
    load_alignment_preset,
    compare_with_preset,
)


def test_alignment_analysis():
    """Test basic alignment analysis with synthetic images."""
    # Create synthetic stereo images with features
    left_img = np.random.randint(0, 255, (480, 640), dtype=np.uint8)
    right_img = np.random.randint(0, 255, (480, 640), dtype=np.uint8)
    
    # Add some common features
    for i in range(20):
        x, y = np.random.randint(100, 540, 2)
        size = np.random.randint(5, 15)
        left_img[y:y+size, x:x+size] = 255
        right_img[y:y+size, x+5:x+5+size] = 255  # Slight offset
    
    try:
        results = analyze_alignment(left_img, right_img, max_features=100)
        
        # Verify result structure
        assert isinstance(results, AlignmentResults)
        assert results.quality in ["EXCELLENT", "GOOD", "ACCEPTABLE", "POOR", "CRITICAL"]
        assert 0 <= results.get_quality_score() <= 100
        assert results.num_matches >= 0
        
        print(f"✓ Alignment analysis test passed (quality: {results.quality}, score: {results.get_quality_score()}%)")
        
    except ValueError as e:
        # Acceptable if not enough features found in random images
        if "Not enough features" in str(e) or "Not enough matches" in str(e):
            print("✓ Alignment analysis test passed (correctly rejected insufficient features)")
        else:
            raise


def test_preset_management(tmp_path):
    """Test saving and loading alignment presets."""
    # Create mock alignment results
    from analysis.camera_alignment import AlignmentResults
    
    results = AlignmentResults(
        vertical_mean_px=2.5,
        vertical_max_px=5.0,
        convergence_std_px=8.2,
        correlation=0.85,
        rotation_deg=1.2,
        num_matches=287,
        scale_difference_percent=3.4,
        scale_ratio=1.034,
        quality="GOOD",
        vertical_status="GOOD",
        horizontal_status="GOOD",
        rotation_status="GOOD",
        scale_status="ACCEPTABLE",
        rotation_correction_needed=False,
        rotation_left=0.0,
        rotation_right=0.0,
        vertical_offset_px=2,
        status_message="Test alignment",
        warnings=[],
        corrections_applied=[]
    )
    
    # Save preset
    preset_name = "test_preset"
    save_alignment_preset(results, preset_name, "left_test", "right_test")
    
    # Load preset
    preset_data = load_alignment_preset(preset_name)
    assert preset_data is not None
    assert preset_data["preset_name"] == preset_name
    assert preset_data["quality_score"] == results.get_quality_score()
    
    # Compare with preset
    comparison = compare_with_preset(results, preset_data)
    assert comparison["trend"] == "SIMILAR"  # Should be similar to itself
    assert comparison["score_delta"] == 0  # Exact match
    
    print("✓ Preset management test passed")


def test_pattern_detection():
    """Test pattern detection with mock session data."""
    from analysis.pattern_detection import PatternDetector
    import json
    import tempfile
    
    # Create mock session directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        session_path = Path(tmp_dir) / "test_session"
        session_path.mkdir()
        
        # Create mock session summary
        mock_data = {
            "pitches": [
                {"pitch_id": "1", "speed_mph": 85.0, "run_in": 2.0, "rise_in": -1.5, "result": "strike"},
                {"pitch_id": "2", "speed_mph": 75.0, "run_in": 3.0, "rise_in": -5.0, "result": "ball"},
                {"pitch_id": "3", "speed_mph": 87.0, "run_in": 1.5, "rise_in": -0.5, "result": "strike"},
                {"pitch_id": "4", "speed_mph": 73.0, "run_in": 4.0, "rise_in": -6.0, "result": "strike"},
                {"pitch_id": "5", "speed_mph": 86.0, "run_in": 2.5, "rise_in": -1.0, "result": "ball"},
            ]
        }
        
        summary_file = session_path / "session_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(mock_data, f)
        
        # Run pattern detection
        detector = PatternDetector()
        report = detector.analyze_session(session_path)
        
        # Verify report
        assert report.total_pitches == 5
        assert report.pitch_types_detected > 0
        assert len(report.pitch_classifications) == 5
        assert 70 < report.average_velocity_mph < 90
        
        # Test report saving
        detector.save_reports(report, session_path)
        assert (session_path / "analysis_report.json").exists()
        assert (session_path / "analysis_report.html").exists()
        
        print("✓ Pattern detection test passed")


if __name__ == '__main__':
    print("Running alignment workflow integration tests...")
    print("=" * 60)
    
    test_alignment_analysis()
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_preset_management(Path(tmp_dir))
    
    test_pattern_detection()
    
    print("=" * 60)
    print("✓ All integration tests passed!")
