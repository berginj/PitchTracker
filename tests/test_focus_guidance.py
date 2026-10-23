"""Turn recommendations require an operator direction and a usable stationary target."""

import cv2
import numpy as np
import pytest

from calib.focus_guidance import FocusGuide


def target(sigma):
    board = ((np.indices((256, 256)).sum(axis=0) // 8) % 2 * 200 + 25).astype(np.uint8)
    return cv2.GaussianBlur(board, (0, 0), sigma)


def settle(guide, image, now=2):
    for _ in range(8):
        advice = guide.observe(image, now=now)
    return advice


@pytest.mark.parametrize("direction,opposite", [("clockwise", "counterclockwise"), ("counterclockwise", "clockwise")])
def test_blurring_the_selected_target_recommends_reversing_the_reported_turn(direction, opposite):
    guide = FocusGuide()
    guide.select_target(0.5, 0.5)
    settle(guide, target(1))
    assert guide.begin_turn(direction, now=0)
    advice = settle(guide, target(3))
    assert "Softer" in advice.message
    assert f"reverse {opposite}" in advice.message
    assert advice.change_percent < -8


def test_sharper_target_confirms_the_operator_direction():
    guide = FocusGuide()
    guide.select_target(0.5, 0.5)
    settle(guide, target(3))
    guide.begin_turn("clockwise", now=0)
    advice = settle(guide, target(1))
    assert "Sharper after clockwise" in advice.message
    assert advice.change_percent > 8


def test_moving_past_the_best_position_recommends_reversing():
    guide = FocusGuide()
    guide.select_target(0.5, 0.5)
    settle(guide, target(3))
    guide.begin_turn("clockwise", now=0)
    settle(guide, target(0.5))
    advice = settle(guide, target(1.5))
    assert "reverse counterclockwise" in advice.message


def test_one_image_cannot_infer_a_lens_direction():
    guide = FocusGuide()
    guide.select_target(0.5, 0.5)
    advice = settle(guide, target(1))
    assert advice.change_percent is None
    assert "Choose Test" in advice.message


@pytest.mark.parametrize("value,word", [(255, "washed out"), (0, "too dark")])
def test_unusable_targets_never_produce_direction_advice(value, word):
    guide = FocusGuide()
    guide.select_target(0.5, 0.5)
    advice = settle(guide, np.full((256, 256), value, dtype=np.uint8))
    assert word in advice.message
    assert advice.score is None
    assert not guide.begin_turn("clockwise")


def test_changing_target_discards_the_old_direction_and_best():
    guide = FocusGuide()
    guide.select_target(0.5, 0.5)
    settle(guide, target(1))
    guide.begin_turn("clockwise")
    guide.select_target(0.6, 0.6)
    advice = settle(guide, target(1))
    assert advice.change_percent is None
    assert "Choose Test" in advice.message


def test_small_noise_changes_do_not_force_a_direction_reversal():
    guide = FocusGuide()
    guide.select_target(0.5, 0.5)
    settle(guide, target(1))
    guide.begin_turn("clockwise", now=0)
    advice = settle(guide, target(1))
    assert "No clear change" in advice.message


def test_unusable_light_discards_the_previous_best_and_turn():
    guide = FocusGuide()
    guide.select_target(0.5, 0.5)
    settle(guide, target(0.5))
    assert guide.begin_turn("clockwise", now=0)
    guide.observe(np.zeros((256, 256), dtype=np.uint8))
    advice = settle(guide, target(3))
    assert advice.best == advice.score
    assert advice.change_percent is None
    assert "Choose Test" in advice.message
