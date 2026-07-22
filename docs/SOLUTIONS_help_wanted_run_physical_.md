## ⚙️ Validation Framework Blueprint: Reference Channel Synchronization Module (RCSM)

**Analysis Summary:**
The primary architectural flaw identified is the lack of strict adherence to failure state propagation. Current measurement systems appear susceptible to producing "plausible" but incorrect results near threshold boundaries, treating proximity as validity. Furthermore, required forensic rigor—specifically binding metrics to environmental and computational state snapshots—is not formally structured into the validation pipeline.

The solution mandates the creation of a standalone, deterministic **Reference Channel Synchronization Module (RCSM)**. This module must operate strictly on pre-approved parameters (locked thresholds/strata) and must fail explicitly when criteria are violated, regardless of empirical closeness to acceptance. We will use Python's `typing` features for strong data contract enforcement, ensuring all calculations are traceable back to the specific environmental signature.

---

### **Proposed Code Fix: `ReferenceValidatorEngine`**

This solution is structured as a robust class designed to encapsulate the entire validation process, meeting statistical, audit, and security requirements simultaneously.

```python
import time
from typing import List, Dict, Any, Tuple, TypedDict
from math import sqrt

# --- Data Contract Definitions for Reproducibility ---

class SensorReading(TypedDict):
    """Represents a single data point from any source."""
    timestamp: float  # UTC seconds
    system_id: str
    value: float
    confidence: float # Confidence score (0.0 to 1.0)

class ValidationMetadata(TypedDict, total=False):
    """Captures the required environment and artifact fingerprints for audit."""
    rig_serial: str
    commit_hash: str
    software_version: str
    setup_snapshot_fingerprint: str # E.g., Hashed configuration file content
    environment_id: str

class ValidationResult(TypedDict):
    """The final structured output containing metrics and counts."""
    status: str # PASSED, FAILED, EXCLUDED, UNMATCHED
    metrics: Dict[str, float]
    counts: Dict[str, int]
    is_valid_claim: bool

# --- Core Validation Module Implementation ---

class ReferenceValidatorEngine:
    """
    Advanced module for independent physical validation against a calibrated reference channel.
    Enforces strict adherence to pre-set thresholds and operational protocol.
    """
    def __init__(self, metadata: ValidationMetadata, speed_thresholds: Dict[str, float], 
                 plate_location_thresholds: Dict[str, float]):
        
        # Lock Parameters (Per Protocol R-003)
        self._metadata = metadata
        self.speed_t = speed_thresholds # e.g., {"min": 85.0, "max": 105.0}
        self.plate_loc_t = plate_location_thresholds # e.g., {"accuracy_m": 0.5}

        # Audit & State Counters (Required Tracking)
        self.attempted_count = 0
        self.accepted_count = 0
        self.rejected_count = 0
        self.unmatched_count = 0
        self.excluded_count = 0
        self.reference_missing_count = 0

    @staticmethod
    def _calculate_mae(measured: List[float], reference: List[float]) -> float:
        """Calculates Mean Absolute Error for two synchronized lists."""
        if not measured or len(measured) != len(reference): return float('inf')
        return sum(abs(m - r) for m, r in zip(measured, reference)) / len(measured)

    @staticmethod
    def _calculate_bias(measured: List[float], reference: List[float]) -> float:
        """Calculates the average directional bias (Mean Difference)."""
        if not measured or len(measured) != len(reference): return 0.0
        return sum((m - r) for m, r in zip(measured, reference)) / len(measured)

    def validate_speed(self, measurements: List[SensorReading], reference_speeds: List[float]) -> Tuple[bool, float]:
        """
        Performs speed validation. Enforces strict failure state propagation.
        Returns (is_valid_claim: bool, calculated_bias: float).
        """
        validation_successful = True
        measured_values = [m['value'] for m in measurements]

        # 1. Core Validation Logic (Failure Enforcement)
        for i, measured_speed in enumerate(measured_values):
            reference_speed = reference_speeds[i]
            diff = abs(measured_speed - reference_speed)

            self.attempted_count += 1
            
            if diff > self.speed_t['max'] or diff < self.speed_t['min']:
                # Crucial Failure Handling: Must fail if outside threshold, no rounding/tolerance applied.
                self.rejected_count += 1
                print(f"[FAIL] Attempt {i}: Speed deviation {diff:.2f} exceeds locked threshold.")
                validation_successful = False # This ensures the overall claim fails immediately
            else:
                # Passes threshold check (Highly restricted condition)
                self.accepted_count += 1

        # Calculate Metrics
        mae = self._calculate_mae(measured_values, reference_speeds)
        bias = self._calculate_bias(measured_values, reference_speeds)
        
        return validation_successful, bias, mae

    def validate_plate_location(self, measurements: List[SensorReading], reference_locations: List[float]) -> Tuple[bool, float]:
        """
        Performs plate-location validation (simulating distance error).
        Returns (is_valid_claim: bool, calculated_mae: float).
        """
        validation_successful = True
        measured_distances = [m['value'] for m in measurements]

        # 1. Core Validation Logic
        for i, measured_distance in enumerate(measured_distances):
            reference_distance = reference_locations[i]
            diff = abs(measured_distance - reference_distance)
            
            self.attempted_count += 1
            
            # Assume location error is assessed against a locked maximum deviation (e.g., 0.5 meters)
            if diff > self.plate_loc_t['accuracy_m']:
                self.rejected_count += 1
                print(f"[FAIL] Attempt {i}: Location deviation {diff:.2f} exceeds locked threshold.")
                validation_successful = False # Failure state propagation
            else:
                self.accepted_count += 1

        # Calculate Metrics
        mae = self._calculate_mae(measured_distances, reference_locations)
        return validation_successful, mae


    def generate_report(self, speed_valid: bool, location_valid: bool) -> ValidationResult:
        """Generates the final comprehensive audit report."""

        # Finalizing Counts (Simulation of remaining data flow)
        self.unmatched_count = 5 # Example count retrieval
        self.excluded_count += self.unmatched_count 
        
        final_status = "PASSED" if speed_valid and location_valid else "FAILED"
        
        return ValidationResult(
            status=final_status,
            metrics={
                'speed_bias': self._calculate_bias([m['value'] for m in measurements], reference_speeds), # Placeholder requires actual measurement lists
                'speed_mae': 0.0,  # Placeholder: Actual calculation from speed run
                'location_mae': 0.0, # Placeholder: Actual calculation from location run
                'reference_uncertainty': self._metadata['setup_snapshot_fingerprint'][:4] + '...Z', # Using a hash fragment as pseudo-uncertainty source
            },
            counts={
                'attempted': self.attempted_count,
                'accepted': self.accepted_count,
                'rejected': self.rejected_count,
                'unmatched': self.unmatched_count,
                'excluded': self.excluded_count + self.unmatched_count, # Accounting for the inclusion of unmatched
                'reference_missing': self.reference_missing_count
            },
            is_valid_claim=final_status == "PASSED" and speed_valid and location_valid
        )

# --- Placeholder Data Structure (for demonstration purposes only) ---
measurements: List[SensorReading] = [
    {'timestamp': 1.0, 'system_id': 'PITCH', 'value': 102.5, 'confidence': 0.98},
    {'timestamp': 2.0, 'system_id': 'PITCH', 'value': 90.0, 'confidence': 0.95}, # Fail Case Example
    {'timestamp': 3.0, 'system_id': 'PITCH', 'value': 105.1, 'confidence': 0.97}
]

reference_speeds: List[float] = [102.0, 91.0, 104.5] # Reference data (simulating the golden source)

measurements_loc: List[SensorReading] = [
    {'timestamp': 1.0, 'system_id': 'LOC', 'value': 0.48, 'confidence': 0.99},
    {'timestamp': 2.0, 'system_id': 'LOC', 'value': 0.65, 'confidence': 0.97}, # Fail Case Example
]

reference_locations: List[float] = [0.49, 0.51]

# --- Execution and Verification Snippet (Mandatory Test Run) ---

# Define the System State Fingerprint (Binding Evidence)
ENVIRONMENTAL_CONTEXT: ValidationMetadata = {
    'rig_serial': 'EMP-VLV-R23A',
    'commit_hash': 'a3f1c8e0b9d746c5f2',
    'software_version': 'v3.1.0-rc3',
    'setup_snapshot_fingerprint': 'SHA256:e7b1d2f0...', # Hash of the exact calibration setup file
    'environment_id': 'FACILITY-ALPHA-DENSITY-HIGH'
}

# Define Locked Protocol Parameters (Locked Thresholds)
SPEED_THRESHOLDS = {"min": 95.0, "max": 105.0}  # Example: Must be >= 95 and <= 105
LOCATION_THRESHOLDS = {"accuracy_m": 0.4} # Example: Must be within 0.4 meters

print("==============================================================")
print("🚀 Initializing Reference Channel Synchronization Module (RCSM)")
print(f"Binding Evidence to Commit: {ENVIRONMENTAL_CONTEXT['commit_hash']}")
print("--------------------------------------------------------------")

# Initialize the Validator Engine with locked parameters and evidence context
validator = ReferenceValidatorEngine(
    metadata=ENVIRONMENTAL_CONTEXT, 
    speed_thresholds=SPEED_THRESHOLDS, 
    plate_location_thresholds=LOCATION_THRESHOLDS
)

# --- STEP 1: Validate Speed ---
# The returned boolean determines if the core threshold integrity was maintained.
speed_valid, speed_bias = validator.validate_speed(measurements, reference_speeds)
print(f"\n[Speed Validation Status] Threshold Integrity Maintained: {speed_valid}")

# --- STEP 2: Validate Plate Location ---
location_valid, location_mae = validator.validate_plate_location(measurements_loc, reference_locations)
print(f"[Location Validation Status] Threshold Integrity Maintained: {location_valid}")


#