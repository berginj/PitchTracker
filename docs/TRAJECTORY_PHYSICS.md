# Trajectory Physics Documentation

This document explains the physics-based trajectory fitting algorithm used in PitchTracker.

## Overview

The trajectory fitter implements a **ballistic motion model with quadratic drag**, which accurately models baseball/softball trajectories through air. The algorithm uses non-linear least squares optimization to fit 3D observations to the physics model.

## Physics Model

### Equations of Motion

The trajectory follows these differential equations:

```
d²x/dt² = -k₀ * v * vₓ
d²y/dt² = -k₀ * v * vᵧ + g
d²z/dt² = -k₀ * v * vᵧ
```

Where:
- `(x, y, z)` = position in feet (X: catcher left-right, Y: vertical, Z: toward plate)
- `v = √(vₓ² + vᵧ² + vᵧ²)` = speed (magnitude of velocity vector)
- `k₀` = drag coefficient (dimensionless, typically 0.08-0.15 for baseball)
- `g = -32.174 ft/s²` = gravitational acceleration (negative Y direction)

### Drag Model

**Quadratic drag** means drag force is proportional to velocity squared: `F_drag ∝ v²`

This is the dominant air resistance regime for baseballs at typical pitching speeds (30-110 mph).

**Why quadratic?**
- At high Reynolds numbers (Re > 1000), drag is dominated by pressure/form drag, not viscous drag
- Baseball at 90 mph has Re ≈ 200,000 (turbulent flow)
- Viscous drag (linear: F ∝ v) only dominates at Re < 1

### State Vector

The optimization solves for an 8-parameter state vector:

```python
params = [x₀, y₀, z₀, vₓ₀, vᵧ₀, vᵧ₀, k₀, Δt]
```

**Position at t=0:**
- `x₀` = initial X position (feet, lateral)
- `y₀` = initial Y position (feet, height)
- `z₀` = initial Z position (feet, distance from plate)

**Velocity at t=0:**
- `vₓ₀` = initial X velocity (ft/s, lateral movement)
- `vᵧ₀` = initial Y velocity (ft/s, vertical movement)
- `vᵧ₀` = initial Z velocity (ft/s, toward plate - typically negative)

**Model parameters:**
- `k₀` = drag coefficient (0.0-0.3 bounded, typical: 0.08-0.12)
- `Δt` = time synchronization offset (seconds, corrects systematic timing bias)

### Parameter Bounds

From `trajectory/physics.py` lines 91-100:

```python
Lower bounds: [-100, -10, -10, -200, -200, -400, 0.0, -Δt_max]
Upper bounds: [+100, +10, +200, +200, +200, +400, 0.3, +Δt_max]
```

**Position bounds (ft):**
- X: ±100 ft (far wider than any field)
- Y: -10 to +10 ft (ground to reasonable height)
- Z: -10 to +200 ft (behind plate to far pitcher's mound)

**Velocity bounds (ft/s):**
- X: ±200 ft/s ≈ ±136 mph (lateral movement)
- Y: ±200 ft/s ≈ ±136 mph (rise/drop)
- Z: -400 to +400 ft/s ≈ -273 to +273 mph (pitch speed + margins)

**Physical bounds:**
- k₀: 0.0 to 0.3 (physically reasonable drag coefficients)
- Δt: ±configured max (typically ±0.01s = ±10ms)

### Initial Seed State

Before optimization, the algorithm computes an initial guess using simple numerical differentiation:

```python
# From _seed_state() function
x₀, y₀, z₀ = positions[0]  # First observation position

# Velocity from finite difference (backward/forward/central)
vₓ = (x[1] - x[0]) / (t[1] - t[0])
vᵧ = (y[1] - y[0]) / (t[1] - t[0])
vᵧ = (z[1] - z[0]) / (t[1] - t[0])
```

This provides a reasonable starting point for the optimizer.

## Optimization Algorithm

### Method: Trust Region Reflective (scipy.optimize.least_squares)

**Algorithm:** `method='trf'` (Trust Region Reflective)
- Handles bounded optimization (respects parameter bounds)
- Robust to poor initial guesses
- Efficient for medium-sized problems (8 parameters)

**Loss function:** `loss='soft_l1'`
- Robust to outliers (downweights large residuals)
- Less sensitive to occasional bad observations
- Better than L2 (least squares) for real-world noisy data

**Jacobian:** `'3-point'` finite difference
- Numerically estimates gradient
- Accurate enough for this problem size
- Could use analytic Jacobian for speed (future optimization)

### Residual Function

The optimizer minimizes the sum of squared residuals between:
1. **Observed positions**: 3D coordinates from stereo triangulation
2. **Predicted positions**: Physics model evaluated at observation times

```python
residual = observed_position - predicted_position(t, params)
```

For N observations with (x, y, z) each: **3N residuals total**

### Convergence Criteria

From `trajectory/physics.py` lines 101-106:

```python
result = least_squares(
    residual_fn,
    params0,
    bounds=bounds,
    method='trf',
    loss='soft_l1',
    ftol=1e-8,    # Function tolerance
    xtol=1e-8,    # Parameter tolerance
    gtol=1e-8,    # Gradient tolerance
    max_nfev=200  # Maximum function evaluations
)
```

**Success conditions:**
- `ftol`: Relative change in cost function < 1e-8
- `xtol`: Relative change in parameters < 1e-8
- `gtol`: Gradient magnitude < 1e-8
- Reaches one of these before `max_nfev` evaluations

## Integration and Prediction

### Forward Integration (ODE Solver)

After optimization, the fitted parameters are used to **propagate the trajectory forward** to predict plate crossing.

From `trajectory/physics.py` lines 130-145:

```python
# Integrate differential equations from t=0 to plate crossing
def rhs(t, state):
    """Right-hand side of ODE system."""
    x, y, z, vx, vy, vz = state
    v = np.sqrt(vx**2 + vy**2 + vz**2)  # Speed

    # Acceleration from drag + gravity
    ax = -k0 * v * vx
    ay = -k0 * v * vy + GRAVITY_FT_S2
    az = -k0 * v * vz

    return [vx, vy, vz, ax, ay, az]
```

**Integration method:**
- Uses `scipy.integrate.solve_ivp` (Runge-Kutta 4/5 adaptive)
- Integrates from release point to plate plane (Z = plate_z_ft)
- Event detection stops integration at plate crossing

### Plate Crossing Prediction

The trajectory is integrated forward until `Z = plate_plane_z_ft` (typically 0.0 ft).

**Plate crossing values:**
- `(x_plate, y_plate)` = lateral position and height at plate
- `t_plate` = time of plate crossing (nanoseconds)
- Used for strike zone determination

## Diagnostics

### Quality Metrics

**RMSE (Root Mean Square Error):**
- **rmse_3d_ft**: 3D position error in feet
- **rmse_px**: Reprojection error in pixels (from stereo triangulation)

**Typical values:**
- Excellent: RMSE < 0.3 ft (< 1 pixel)
- Good: RMSE < 0.5 ft (1-2 pixels)
- Acceptable: RMSE < 1.0 ft (2-4 pixels)
- Poor: RMSE > 1.0 ft

**Drag parameter validation:**
```python
drag_param_ok = (0.01 <= k0 <= 0.25)
```
- Outside this range suggests optimization failure
- Baseball drag typically 0.08-0.12
- Softball drag typically 0.06-0.10

### Failure Codes

From `trajectory/contracts.py`:

```python
class FailureCode(str, Enum):
    INSUFFICIENT_POINTS = "insufficient_points"       # < 4 observations
    OPT_DID_NOT_CONVERGE = "opt_did_not_converge"    # Optimizer failed
    INTEGRATION_FAILED = "integration_failed"         # ODE solver failed
    RADAR_DISAGREEMENT = "radar_disagreement"         # Speed != radar reading
```

### Confidence Scoring

From `trajectory/confidence.py` - combines multiple quality signals:

1. **Trajectory fit quality** (RMSE, residuals)
2. **Number of observations** (more = higher confidence)
3. **Temporal distribution** (no large gaps)
4. **Drag parameter validity** (physical range)
5. **Radar agreement** (if radar speed available)

Final confidence: `0.0` (no confidence) to `1.0` (perfect confidence)

## Constants and Configuration

### Physical Constants

```python
GRAVITY_FT_S2 = -32.174  # ft/s² (standard gravity, negative Y)
```

### Default Values

From `trajectory/contracts.py`:

```python
class TrajectoryFitRequest:
    drag_k0: float = 0.1                     # Default drag coefficient
    plate_plane_z_ft: float = 0.0            # Plate at Z=0
    time_offset_bounds_ms: float = 10.0      # ±10ms time sync tolerance
    fiducial_time_offset_ns: int | None = None  # Known timing offset
    radar_speed_mph: float | None = None     # Radar speed for validation
    radar_speed_ref: str = "release"         # "release" or "plate"
```

### Coordinate System

```yaml
coordinate_system: "X: catcher left-right, Y: vertical, Z: toward plate"
```

**Convention:**
- **X**: Positive = catcher's right, Negative = catcher's left
- **Y**: Positive = up, Negative = down
- **Z**: Positive = toward plate, Negative = toward pitcher

**Reference frames:**
- Origin typically at plate center at ground level
- Release point: high Y (5-7 ft), high Z (50-60 ft)
- Plate crossing: variable X (±17 in), variable Y (2-5 ft), Z ≈ 0 ft

## Performance Considerations

### Computational Cost

**Typical trajectory fit:**
- 10-20 observations
- 8 parameters
- ~20-50 function evaluations
- **Total time: 5-20 milliseconds**

**Factors affecting speed:**
- Number of observations (linear scaling)
- Optimization convergence (varies with data quality)
- ODE integration steps (adaptive, depends on trajectory)

### Real-time vs. Batch

**Real-time mode** (`realtime=True`):
- May fit with partial trajectory (>6 points)
- Returns intermediate results for live display
- Lower confidence, may be revised

**Batch mode** (`realtime=False`):
- Waits for complete trajectory
- Uses all observations for best accuracy
- Final confidence and diagnostics

## Accuracy and Limitations

### Sources of Error

1. **Stereo triangulation error**: ±0.5-2 pixels → ±0.1-0.5 ft at distance
2. **Timing error**: ±1ms → ±0.1 ft error at 90 mph
3. **Model simplification**:
   - Ignores spin effects (Magnus force)
   - Ignores wind
   - Assumes constant drag coefficient (actually varies with speed)
   - Assumes standard air density

4. **Calibration drift**: Focal length changes, baseline measurement error

### Typical Accuracy

**Position at plate:**
- X (horizontal): ±0.5 inch
- Y (vertical): ±0.5 inch
- Good enough for strike zone determination

**Velocity:**
- ±1-2 mph (with good observations)
- ±3-5 mph (with sparse or noisy observations)

**Movement (break):**
- ±0.5 inch (horizontal and vertical)
- Sufficient for pitch classification

## Future Improvements

### Potential Enhancements

1. **Spin model**: Add Magnus force for curveballs/sliders
   ```
   F_Magnus = S * (ω × v)
   ```
   Requires additional spin rate measurements

2. **Analytic Jacobian**: Replace finite differences with closed-form derivatives
   - 2-3x faster optimization

3. **Multi-segment drag**: Different k₀ for different speed ranges
   - More accurate for large speed variations

4. **Environmental corrections**: Temperature, pressure, humidity
   - Affects air density and drag

5. **Bayesian inference**: Uncertainty quantification
   - Parameter covariance matrix
   - Prediction intervals at plate

## References

### Physics

1. **Cross, R.** "The aerodynamics of baseball" (American Journal of Physics, 2008)
   - Detailed drag coefficient measurements

2. **Nathan, A.M.** "The effect of spin on the flight of a baseball" (American Journal of Physics, 2008)
   - Magnus force and spin decay

### Optimization

3. **scipy.optimize.least_squares** documentation
   - https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html

4. **Byrd, R.H., et al.** "A trust region method based on interior point techniques for nonlinear programming" (1999)
   - Theory behind Trust Region Reflective algorithm

---

**File Location**: `trajectory/physics.py`
**Related Files**:
- `trajectory/contracts.py` - Data structures
- `trajectory/confidence.py` - Confidence scoring
- `trajectory/base.py` - Base class

**Last Updated**: 2026-02-13
**Maintainer**: See git history
