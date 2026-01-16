"""Base trajectory fitter interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from contracts import StereoObservation
from trajectory.contracts import TrajectoryFitRequest, TrajectoryFitResult


class TrajectoryFitterBase(ABC):
    def __init__(self) -> None:
        self._request: Optional[TrajectoryFitRequest] = None
        self._buffer: List[StereoObservation] = []

    def reset(self, request: TrajectoryFitRequest) -> None:
        self._request = request
        self._buffer = list(request.observations)

    def add_observation(self, obs: StereoObservation) -> None:
        self._buffer.append(obs)

    def add_observations(self, observations: List[StereoObservation]) -> None:
        self._buffer.extend(observations)

    @abstractmethod
    def maybe_fit(self) -> Optional[TrajectoryFitResult]:
        raise NotImplementedError

    @abstractmethod
    def finalize_fit(self) -> TrajectoryFitResult:
        raise NotImplementedError
