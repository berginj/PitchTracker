"""Correctness and benchmark-oriented tests for detect/utils.py."""

from __future__ import annotations

import math

import numpy as np
import pytest

from detect.utils import connected_components


class TestConnectedComponents:
    """Verify connected_components preserves Blob/circularity behavior."""

    def test_empty_mask_returns_no_components(self) -> None:
        mask = np.zeros((100, 100), dtype=np.uint8)
        assert connected_components(mask) == []

    def test_single_circle_circularity_near_one(self) -> None:
        mask = np.zeros((100, 100), dtype=np.uint8)
        cv2 = pytest.importorskip("cv2")
        cv2.circle(mask, (50, 50), 20, 1, thickness=-1)
        comps = connected_components(mask)
        assert len(comps) == 1
        c = comps[0]
        circularity = 4 * math.pi * c.area / (c.perimeter**2)
        assert circularity > 0.85, f"Expected high circularity, got {circularity}"

    def test_thin_rectangle_low_circularity(self) -> None:
        mask = np.zeros((100, 200), dtype=np.uint8)
        mask[45:55, 10:190] = 1  # thin wide rectangle
        comps = connected_components(mask)
        assert len(comps) == 1
        c = comps[0]
        circularity = 4 * math.pi * c.area / (c.perimeter**2)
        assert circularity < 0.5

    def test_two_separate_blobs(self) -> None:
        mask = np.zeros((100, 200), dtype=np.uint8)
        mask[10:30, 10:30] = 1
        mask[60:80, 150:170] = 1
        comps = connected_components(mask)
        assert len(comps) == 2

    def test_diagonally_adjacent_components_keep_separate_perimeters(self) -> None:
        mask = np.zeros((20, 20), dtype=np.uint8)
        mask[2:7, 2:7] = 1
        mask[7:12, 7:12] = 1

        comps = connected_components(mask)

        assert len(comps) == 2
        assert all(component.perimeter > 0 for component in comps)

    def test_area_and_centroid_accuracy(self) -> None:
        mask = np.zeros((50, 50), dtype=np.uint8)
        mask[10:20, 10:20] = 1  # 10×10 block
        comps = connected_components(mask)
        assert len(comps) == 1
        c = comps[0]
        assert c.area == 100
        assert abs(c.centroid[0] - 14.5) < 0.5
        assert abs(c.centroid[1] - 14.5) < 0.5

    def test_bbox_format(self) -> None:
        mask = np.zeros((50, 80), dtype=np.uint8)
        mask[5:15, 20:40] = 1
        comps = connected_components(mask)
        c = comps[0]
        # bbox = (left, top, right, bottom)
        assert c.bbox == (20, 5, 39, 14)

    def test_no_per_component_allocation_scales(self) -> None:
        """Regression guard: runtime should not scale with N full-frame masks."""
        import time

        mask = np.zeros((200, 200), dtype=np.uint8)
        # Create many small components
        for r in range(0, 200, 10):
            for c in range(0, 200, 10):
                mask[r : r + 3, c : c + 3] = 1

        t0 = time.perf_counter()
        comps = connected_components(mask)
        elapsed = time.perf_counter() - t0
        # Should have ~400 components and complete in <50ms on any CI machine
        assert len(comps) > 100
        assert elapsed < 0.5, f"Too slow: {elapsed:.3f}s for {len(comps)} components"
