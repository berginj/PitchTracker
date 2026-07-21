# Detection Algorithms Documentation

This document explains the ball detection algorithms used in PitchTracker for real-time baseball/softball tracking.

## Overview

PitchTracker supports two detection approaches:
1. **Classical CV Detection** (default, recommended) - Frame differencing with blob analysis
2. **ML Detection** (experimental) - YOLOv5-based object detection

Both approaches process 60 FPS stereo video in real-time, extracting ball position with sub-pixel accuracy.

## Classical Detection

The classical detector uses **background subtraction** and **blob analysis** to detect moving circular objects. It operates in two modes with different sensitivity/accuracy tradeoffs.

### Mode A: Dual Frame Differencing (Default)

**Algorithm Overview:**
```
1. Convert frame to grayscale
2. Compute frame-to-frame difference (temporal)
3. Compute background difference (spatial)
4. Combine masks: foreground = (frame_diff > threshold) OR (bg_diff > threshold)
5. Update background model with exponential moving average
6. Extract connected components (blobs)
7. Filter by area, circularity, velocity
8. Return detections
```

**Key Parameters** (from `configs/default.yaml`):

```yaml
detector:
  mode: MODE_A
  frame_diff_threshold: 18.0    # Temporal sensitivity
  bg_diff_threshold: 12.0       # Spatial sensitivity
  bg_alpha: 0.08                # Background update rate (0-1)
  filters:
    min_area: 12                 # Minimum blob area (pixels)
    min_circularity: 0.1         # Minimum circularity (0-1)
```

**Frame Differencing:**
```python
# Temporal: Detects motion between consecutive frames
diff = |gray[t] - gray[t-1]|
frame_mask = diff > frame_diff_threshold

# Spatial: Detects objects different from background
bg_diff = |gray[t] - background|
bg_mask = bg_diff > bg_diff_threshold

# Combined
foreground = frame_mask | bg_mask
```

**Background Model:**
```python
# Exponential moving average (EMA)
background[t] = alpha * gray[t] + (1 - alpha) * background[t-1]
```

- `alpha = 0.08` (8%) → slow adaptation, stable background
- Higher alpha → faster adaptation, less stable
- Lower alpha → slower adaptation, more stable

**Memory Optimization:**
- Background stored as `uint8` (1 byte per pixel)
- Computation done in `float32` for precision
- Conversion: `uint8` → `float32` → compute → `uint8`
- **Memory savings: 75%** vs storing as float32

**Advantages:**
- ✅ Fast: ~3-5 ms per frame (1280×720)
- ✅ Robust to lighting changes (background adaptation)
- ✅ Dual thresholding reduces false positives
- ✅ Works well for fast-moving objects

**Disadvantages:**
- ❌ Sensitive to camera motion (stationary cameras required)
- ❌ Can miss slow-moving objects (frame diff too small)
- ❌ Requires tuning thresholds for different lighting

### Mode B: Edge-Enhanced Background Subtraction

**Algorithm Overview:**
```
1. Convert frame to grayscale
2. Extract edges using Sobel filter
3. Create edge mask: edges > edge_threshold
4. Compute background difference: |gray - background|
5. Create blob mask: bg_diff > blob_threshold
6. Combine masks: foreground = edge_mask | blob_mask
7. Update background model
8. Extract connected components
9. Filter and return detections
```

**Key Parameters:**

```yaml
detector:
  mode: MODE_B
  edge_threshold: 32.0          # Edge detection sensitivity
  blob_threshold: 22.0          # Blob detection sensitivity
  bg_alpha: 0.08                # Background update rate
```

**Edge Detection (Sobel):**
```python
# Sobel filter computes gradient magnitude
edges = sqrt((dI/dx)² + (dI/dy)²)
edge_mask = edges > edge_threshold
```

**Hybrid Mask:**
```python
# Edges capture ball boundaries
# Blob diff captures interior
foreground = edge_mask | blob_mask
```

**Advantages:**
- ✅ Better edge definition (sharper boundaries)
- ✅ Works with lower contrast balls
- ✅ Less sensitive to illumination gradients
- ✅ Good for textured balls

**Disadvantages:**
- ❌ Slower than Mode A (~5-8 ms per frame)
- ❌ More false positives from background edges
- ❌ Requires higher computational resources

### Connected Components Analysis

Both modes extract blobs using **connected components** labeling:

```python
def connected_components(binary_mask):
    """
    Find connected regions in binary mask.

    Returns:
        List of Component objects with:
        - centroid: (cx, cy) in pixels
        - area: number of pixels
        - perimeter: boundary length
        - bbox: (x, y, width, height)
    """
```

**Circularity Metric:**
```python
circularity = 4π × area / perimeter²
```

- Circle: circularity = 1.0
- Square: circularity ≈ 0.785
- Line: circularity → 0

**Typical ranges:**
- Baseball: 0.7-1.0 (nearly circular)
- Background noise: 0.1-0.5 (irregular)
- Filter threshold: 0.1 (min_circularity)

### Filtering Pipeline

After blob extraction, detections are filtered:

**1. Area Filter:**
```python
min_area <= blob.area <= max_area (if specified)
```

**Typical values:**
- min_area: 12 pixels (3×4 pixel blob at distance)
- max_area: None (no upper limit by default)

**2. Circularity Filter:**
```python
min_circularity <= blob.circularity <= max_circularity (if specified)
```

**Typical values:**
- min_circularity: 0.1 (very lenient, filters obvious non-circles)
- max_circularity: None (no upper limit)

**3. Velocity Filter:**
```python
min_velocity <= blob.velocity <= max_velocity (if specified)
```

**Velocity calculation:**
```python
velocity = sqrt((x[t] - x[t-1])² + (y[t] - y[t-1])²)
```

**Typical values:**
- min_velocity: 0.0 (no minimum by default)
- max_velocity: None (no maximum)

**4. Consecutive Hits Filter:**
```python
if consecutive_hits < min_consecutive:
    return []  # Suppress detection
```

**Typical values:**
- min_consecutive: 2 (require timestamp-consistent detections across frames)
- Higher values (2-3) reduce false positives but increase latency

### ROI Cropping

Each camera can have a Region of Interest (ROI) to reduce processing area:

**Benefits:**
- ✅ Faster processing (smaller image)
- ✅ Fewer false positives (ignore background)
- ✅ Focus on relevant area

**Implementation:**
```python
# Crop to ROI
cropped, offset = crop_to_roi(image, roi_polygon)

# Process cropped image
detections = detect(cropped)

# Offset detections back to original coordinates
for det in detections:
    det.x += offset[0]
    det.y += offset[1]
```

### Performance Characteristics

**Mode A (Dual Frame Differencing):**
- **Processing time**: 3-5 ms per frame (1280×720)
- **Memory**: ~2 MB per camera (background buffer)
- **CPU**: ~10-15% per camera @ 60 FPS (single core)

**Mode B (Edge-Enhanced):**
- **Processing time**: 5-8 ms per frame (1280×720)
- **Memory**: ~2 MB per camera (background buffer)
- **CPU**: ~15-20% per camera @ 60 FPS (single core)

**Scalability:**
- Processing time scales linearly with resolution
- 640×480 → ~2 ms (Mode A)
- 1920×1080 → ~8 ms (Mode A)

## ML Detection (Experimental)

The ML detector uses **YOLOv5** (You Only Look Once) for object detection.

### Architecture

**Model:** YOLOv5s (small variant)
- Input: 640×640 RGB image
- Output: Bounding boxes + confidence scores
- Class: "ball" (single class detection)

**Inference Pipeline:**
```
1. Resize frame to 640×640
2. Normalize pixels (0-255 → 0-1)
3. Run ONNX inference
4. Parse YOLO output (grid predictions)
5. Apply NMS (non-maximum suppression)
6. Filter by confidence threshold
7. Convert boxes to centroids
8. Return detections
```

**Configuration:**
```yaml
detector:
  type: ml
  model_path: models/yolov5s_ball.onnx
  model_input_size: [640, 640]
  model_conf_threshold: 0.25      # Confidence threshold
  model_class_id: 0                # Ball class ID
  model_format: yolo_v5
```

### ONNX Runtime

**Requirements:**
```bash
pip install onnxruntime  # CPU version
pip install onnxruntime-gpu  # GPU version (CUDA required)
```

**Model loading:**
```python
import onnxruntime as ort

session = ort.InferenceSession(
    model_path,
    providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
)
```

**Inference:**
```python
outputs = session.run(
    None,  # All outputs
    {'images': preprocessed_frame}
)
```

### Non-Maximum Suppression (NMS)

**Purpose:** Remove duplicate detections of the same ball

**Algorithm:**
```
1. Sort boxes by confidence (high to low)
2. Pick highest confidence box
3. Remove all boxes with IoU > threshold (e.g., 0.5)
4. Repeat until no boxes remain
```

**IoU (Intersection over Union):**
```python
IoU = area(box1 ∩ box2) / area(box1 ∪ box2)
```

### Performance Characteristics

**CPU Inference (onnxruntime):**
- **Processing time**: 40-60 ms per frame (YOLOv5s)
- **Latency**: ~2-3 frame delay @ 60 FPS
- **CPU usage**: ~80-100% (single core maxed)
- **Not recommended for real-time**

**GPU Inference (onnxruntime-gpu):**
- **Processing time**: 8-15 ms per frame (YOLOv5s on GTX 1080)
- **Latency**: Acceptable for real-time
- **GPU usage**: ~20-30% (small model)
- **Requires CUDA GPU**

### Advantages vs. Classical

- ✅ Trained on real baseball images
- ✅ Better handling of complex backgrounds
- ✅ More robust to lighting variations
- ✅ Works with moving cameras (in theory)

### Disadvantages vs. Classical

- ❌ Much slower (10-20x on CPU)
- ❌ Requires GPU for real-time performance
- ❌ Requires model training/retraining
- ❌ Larger memory footprint (~30 MB model)
- ❌ Less predictable latency

## Detection Health Monitoring

Both detectors track **detection health**:

```python
@dataclass
class DetectorHealth:
    last_detection_ns: int        # Timestamp of last detection
    time_since_detection_ms: float  # Time since last detection (ms)
    consecutive_hits: int          # Consecutive frames with detections
    is_healthy: bool              # Overall health status
```

**Health criteria:**
```python
is_healthy = time_since_detection_ms < 5000  # < 5 seconds
```

## Comparison Table

| Feature | Classical (Mode A) | Classical (Mode B) | ML (YOLOv5) |
|---------|-------------------|-------------------|-------------|
| **Speed (CPU)** | 3-5 ms | 5-8 ms | 40-60 ms |
| **Speed (GPU)** | N/A | N/A | 8-15 ms |
| **Memory** | 2 MB | 2 MB | 30 MB |
| **Accuracy** | High (tuned) | High (tuned) | Very High |
| **Robustness** | Medium | Medium-High | High |
| **False Positives** | Low (filtered) | Medium | Low |
| **Setup Complexity** | Low | Low | High |
| **Hardware Requirements** | Any CPU | Any CPU | GPU recommended |
| **Recommended For** | **Production** | **Production** | Research/Offline |

## Tuning Guide

### Classical Detection Tuning

**Problem: Missing detections (false negatives)**

Solutions:
1. **Lower thresholds**:
   ```yaml
   frame_diff_threshold: 15.0  # Was 18.0
   bg_diff_threshold: 10.0     # Was 12.0
   ```

2. **Reduce min_area**:
   ```yaml
   min_area: 8  # Was 12
   ```

3. **Increase background adaptation**:
   ```yaml
   bg_alpha: 0.12  # Was 0.08 (faster adaptation)
   ```

**Problem: Too many false positives**

Solutions:
1. **Raise thresholds**:
   ```yaml
   frame_diff_threshold: 20.0  # Was 18.0
   bg_diff_threshold: 15.0     # Was 12.0
   ```

2. **Increase min_area**:
   ```yaml
   min_area: 16  # Was 12
   ```

3. **Increase min_circularity**:
   ```yaml
   min_circularity: 0.3  # Was 0.1 (stricter circle requirement)
   ```

4. **Add consecutive hits requirement**:
   ```yaml
   min_consecutive: 2  # Was 1 (require 2 consecutive detections)
   ```

**Problem: Background artifacts**

Solutions:
1. **Slower background adaptation**:
   ```yaml
   bg_alpha: 0.05  # Was 0.08 (more stable background)
   ```

2. **Use ROI cropping** to exclude problematic areas

3. **Improve lighting** (consistent, uniform illumination)

### ML Detection Tuning

**Problem: Low confidence scores**

Solutions:
1. **Lower confidence threshold**:
   ```yaml
   model_conf_threshold: 0.15  # Was 0.25
   ```

2. **Retrain model** with more data

**Problem: Too slow on CPU**

Solutions:
1. **Switch to GPU** (onnxruntime-gpu)
2. **Use smaller model** (YOLOv5n instead of YOLOv5s)
3. **Reduce input size**:
   ```yaml
   model_input_size: [416, 416]  # Was [640, 640]
   ```
4. **Use classical detector instead** (recommended)

## Best Practices

### For Optimal Performance

1. **Use classical detector** (Mode A) for production
2. **Tune thresholds** for your specific lighting conditions
3. **Use ROI cropping** to focus on relevant areas
4. **Mount cameras stably** (vibration reduces accuracy)
5. **Provide consistent lighting** (avoid shadows, flicker)

### For Best Accuracy

1. **Calibrate cameras properly** (see AUTO_CALIBRATION.md)
2. **Use high FPS** (60 FPS recommended, 30 FPS minimum)
3. **Tune for your ball type** (baseball vs softball have different sizes)
4. **Test and iterate** on real pitch data
5. **Monitor detection health** in real-time

### For Debugging

1. **Enable target overlay** to visualize detections
2. **Check logs** for detection statistics
3. **Review recorded sessions** to identify missed pitches
4. **Adjust one parameter at a time** when tuning
5. **Compare before/after** on same test dataset

## Implementation Files

**Classical Detector:**
- `detect/classical_detector.py` - Main detector class
- `detect/modes.py` - Mode A and Mode B implementations
- `detect/filters.py` - Blob filtering
- `detect/utils.py` - Connected components, edge detection
- `detect/config.py` - Configuration dataclass

**ML Detector:**
- `detect/ml_detector.py` - YOLOv5 detector class
- `detect/onnx_loader.py` - ONNX model loading
- `detect/yolo_parser.py` - YOLO output parsing

**Common:**
- `detect/detector.py` - Base detector interface
- `detect/types.py` - Detection dataclasses
- `configs/default.yaml` - Configuration file

## References

### Classical CV

1. **Stauffer & Grimson** (1999) - "Adaptive background mixture models for real-time tracking"
   - Original background subtraction paper

2. **Zivkovic** (2004) - "Improved adaptive Gaussian mixture model for background subtraction"
   - Modern background modeling

### ML Detection

3. **Redmon et al.** (2016) - "You Only Look Once: Unified, Real-Time Object Detection"
   - YOLO paper

4. **Ultralytics YOLOv5** - https://github.com/ultralytics/yolov5
   - Implementation used

---

**Last Updated**: 2026-02-13
**Maintainer**: See git history
