# PitchTracker glossary

This page explains the project’s most common technical terms in plain
language. It is written for operators, coaches, field testers, and contributors
who do not need to know the implementation details before getting started.

| Term | Plain-language meaning |
|---|---|
| **Global shutter** | A camera exposure method that captures the image at the same instant across the whole sensor. It helps reduce motion distortion. The software cannot prove a camera is global shutter from its name alone; physical testing is required. |
| **Rolling shutter** | A camera exposure method that reads the image in rows at different times. Fast motion can appear bent or shifted. |
| **Stereo camera pair** | Two cameras viewing the same pitch lane from different positions so the system can estimate depth. |
| **UVC camera** | A USB Video Class camera that Windows and common capture libraries can access without a custom application-specific driver. |
| **Setup workflow** | The guided process that selects cameras, checks capture quality, calibrates the pair, aligns the field, and saves the configuration. |
| **Rig profile** | The saved configuration for one physical installation, including camera identities, calibration, field alignment, controls, and artifact hashes. |
| **Setup snapshot** | An immutable record of the evidence used to decide whether a rig is ready to run. |
| **Field transform** | The measured relationship between camera coordinates and the physical pitching area. |
| **ROI (region of interest)** | The part of an image where the system expects useful information, such as the pitch lane or plate area. |
| **ChArUco** | A printed calibration target that combines chessboard geometry with fiducial markers to help cameras find known points. |
| **Pair-skew** | The time difference between the left and right frames treated as one stereo pair. Tail values such as p95 and p99 show occasional bad timing, not just the average. |
| **Reference device** | An independent, calibrated measurement system used to compare PitchTracker results. It must not rely on PitchTracker’s detections or calibration. |
| **Shadow dataset** | Development data that may be used to tune software or calibration. It cannot support a final accuracy claim. |
| **Confirmation dataset** | A separate, frozen dataset collected after tuning. It is the dataset that can support an accuracy review. |
| **Evidence package** | The recorded files and metadata that let someone inspect what the system saw, decided, rejected, or could not measure. |
| **Denominator** | The full set of opportunities counted in a rate. Rejected, unmatched, and unavailable cases remain in the denominator. |
| **Raw value** | The value produced before an allowed correction is applied. Raw values remain available for review. |
| **Correction** | A bounded, recorded adjustment applied when the system can observe and justify a known issue. It is not a license to hide an error. |
| **Preflight** | A check that the current rig, software, calibration, controls, and evidence are still eligible before recording. |
| **Operationally eligible** | Safe to run under the configured setup rules. This does not mean physically accurate. |
| **Validated** | Supported by an approved physical confirmation dataset and an active approval for the exact rig and software. Automated tests alone cannot make a result validated. |
| **Estimated** | A result exists, but physical accuracy has not been established for the exact setup. |
| **Degraded** | A result exists with a material, disclosed limitation. |
| **Rejected** | A result was produced but failed a quality gate. It remains visible in evidence and counts. |
| **Unavailable** | The required evidence or measurement was not produced. It is not the same as zero. |

For the complete evidence and approval rules, see [Evidence-First Field
Robustness](EVIDENCE_FIRST_FIELD_ROBUSTNESS.md) and [Physical Validation Protocol
v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md).
