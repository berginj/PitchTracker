"""Optional compiled float64 residual and discrete sensitivity evaluator."""

from __future__ import annotations

from importlib import import_module
from contextvars import ContextVar
from typing import Any

import numpy as np
from trajectory.compute_backend import QualifiedEvaluator

evaluator_factory: ContextVar[Any] = ContextVar("trajectory_evaluator_factory", default=None)


def native_module() -> Any | None:
    try:
        return import_module("_pitchtracker_native")
    except ImportError:
        return None


class NativeResidual:
    def __init__(self, request, times, positions, whiteners):
        self.module = native_module()
        self.inputs = (
            np.ascontiguousarray(times),
            np.ascontiguousarray(positions),
            np.ascontiguousarray(whiteners),
            np.asarray(request.wind_ft_s or (0.0, 0.0, 0.0), dtype=float),
            request.drag_k0,
            max(request.drag_sigma, 1e-6),
            request.drag_prior_enabled,
        )
        self._parameters = None
        self._value = None
        factory = evaluator_factory.get()
        self.evaluator = (
            factory(self.module, self.inputs, request)
            if factory
            else QualifiedEvaluator(
                self.module,
                self.inputs,
                request.compute_backend,
                request.compute_concurrency,
            )
        )

    def evaluate(self, parameters):
        if self._parameters is None or not np.array_equal(parameters, self._parameters):
            self._value = self.evaluator.evaluate(np.ascontiguousarray(parameters))
            self._parameters = np.array(parameters, copy=True)
        return self._value

    def residual(self, parameters):
        # SciPy robust-loss transformations mutate residual/Jacobian arrays.
        return self.evaluate(parameters)[0].copy()

    def jacobian(self, parameters):
        return self.evaluate(parameters)[1].copy()
