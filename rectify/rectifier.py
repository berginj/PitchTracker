"""Rectification interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from contracts import Frame


class Rectifier(ABC):
    @abstractmethod
    def rectify(self, frame: Frame) -> Frame:
        """Rectify an input frame."""
