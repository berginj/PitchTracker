# Trajectory model and measurement limits

Updated 2026-09-08. This describes implementation, not physical accuracy.
Independent confirmation remains required by
[Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md).

## Stereo model

`trajectory/physics.py` integrates position and velocity using RK4:

```text
dr/dt = v
dv/dt = (0, -32.174, 0) - k * |v - wind| * (v - wind)
```

Position is feet, velocity feet/second, time seconds. Thus `k` is inverse feet,
not a dimensionless aerodynamic coefficient. Positive Y is up. Incoming
tracks normally approach decreasing Z toward the configured plate plane.
The calibrated field transform defines world axes, not raw camera pixels.

Seven parameters are estimated: position and velocity at the first observed
timestamp, plus `k`. Default `k=0.002 ft^-1` is an optimizer seed unless
`drag_prior_enabled` is explicitly enabled. Search bounds are not a validated
physical range. A shared time translation is degenerate with initial state
and is fixed at zero; this cannot recover unknown exposure times.

Residuals use observation covariance whitening. Missing covariance or legacy
depth-only zero-variance axes use `observation_sigma_ft` (default 0.02 ft),
labeled `assumed_or_partial`. This is assumed noise, not measured system
uncertainty. Bounded least squares uses Huber loss, `f_scale=1.5`, and Jacobian
scaling. Trajectories are evaluated at observation timestamps.

Crossing is interpolated where fitted samples bracket the plate, not
extrapolated from an unobserved release point. Strike-volume calculation
separately uses a continuous piecewise-linear swept sphere between observations,
with a 50 ms maximum gap. Unsupported coverage must not become a ball call.

## Eligibility and confidence

Nonconvergence, invalid input, missing crossing, nonmonotonic depth,
unidentifiable speed, and detected model mismatch make a fit unusable.
`speed_std_assuming_model_mph` is local Jacobian-based uncertainty conditional
on assumed noise and the force model. Its default 2 mph rejection threshold is
an engineering gate, not a verified speed-error bound.

Legacy `confidence` now means heuristic fit quality; `fit_quality_score`
names that meaning explicitly. `expected_plate_error_ft` remains unavailable:
residuals alone cannot produce physical prediction intervals. Calibration,
correlated noise, exposure skew, and missing forces can bias low-residual fits.

## Speed provenance

Vision speed describes the first fitted observed point, with field Z and
timestamp. It is not release speed. Manual/radar readings remain separate.
Legacy `speed_mph` is the selected display value; validation uses the separate
provenance records. Unknown external locations remain unspecified. An assisted
estimator cannot validate independent vision against its own input instrument.

## Ray modes and missing physics

`ray_reprojection` and `ray_graph` remain comparison-first and require a
proven calibration-to-field transform. Current ray propagation is gravity-only:
the legacy drag parameter does not affect propagation and is not reported as a
measured drag coefficient. Directly radar-constrained fits are labeled
`radar_assisted`.

Neither model estimates spin or general transverse force. Independent
`solve_ivp` regressions cover noiseless 30/60/90 mph stereo tracks, 0.1/0.3 s
windows, seed sensitivity, uncertain observations, and omitted transverse force.
Passing these numerical cases does not establish a physical operating envelope.

The fixed-seed noisy sweep (`python -m benchmarks.trajectory_model_envelope`)
found all six zero-transverse-force cases eligible, with absolute speed error
at most 0.133 mph in those synthetic inputs. Adding 30 ft/s² transverse force
was detected as model mismatch in all three 0.3 s windows but not in the three
0.1 s windows. This is direct evidence that a passing short-arc fit does not
prove the force model is correct. Do not generalize these numbers into an
accuracy bound: only 12 cases and one noise seed were evaluated.

## Runtime limits

The analyzer supervises one-shot children: default 15 seconds stereo and
10 seconds per ray fit, including startup. Timeout kills/reaps the child and
returns `DEADLINE_EXCEEDED`; valid stereo fallback may still be used.
Offline direct fitter calls do not provide this process boundary. Queue wait
is additional to service latency. Measure both on target hardware; historical
millisecond latency and sub-inch accuracy claims were not established.
