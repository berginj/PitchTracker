from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Component:
    area: int
    perimeter: int
    centroid: tuple[float, float]
    bbox: tuple[int, int, int, int]


def to_grayscale(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 3:
        return frame.mean(axis=2, dtype=np.float32)
    return frame.astype(np.float32, copy=False)


def compute_focus_score(image: np.ndarray) -> float:
    """Compute focus quality score using variance of Laplacian method.

    This is the industry-standard autofocus metric. Higher values indicate
    better focus (more edge detail/sharpness).

    Args:
        image: Grayscale or color image (converted to grayscale if color)

    Returns:
        Focus quality score (typically 0-1000+ for in-focus images,
        <100 for severely out-of-focus images)

    Note:
        - Uses OpenCV Laplacian (second derivative) to detect edges
        - Variance of Laplacian correlates with sharpness
        - Fast enough for real-time feedback (~1ms per frame)
    """
    import cv2

    # Convert to grayscale if needed
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Compute Laplacian (second derivative - measures edge strength)
    # ksize=3 is standard for focus measurement
    laplacian = cv2.Laplacian(gray, cv2.CV_64F, ksize=3)

    # Compute variance of Laplacian
    # Higher variance = more edges/detail = better focus
    focus_measure = laplacian.var()

    return float(focus_measure)


def connected_components(mask: np.ndarray) -> list[Component]:
    """Find connected components using OpenCV connectedComponentsWithStats.

    Computes each perimeter within its component bounding box, avoiding the
    previous per-component full-frame allocation while preserving
    four-connected component semantics.

    Args:
        mask: Binary mask (non-zero values considered foreground)

    Returns:
        List of Component objects with area, perimeter, centroid, and bbox
    """
    import cv2

    mask_uint8 = mask.astype(np.uint8)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_uint8, connectivity=4)
    if num_labels <= 1:
        return []

    components: list[Component] = []
    for i in range(1, num_labels):
        left, top, width, height, area = stats[i]
        centroid = (float(centroids[i][0]), float(centroids[i][1]))
        bbox = (left, top, left + width - 1, top + height - 1)
        component_mask = (labels[top : top + height, left : left + width] == i).astype(np.uint8)
        contours, _ = cv2.findContours(component_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        perimeter = int(sum(cv2.arcLength(contour, closed=True) for contour in contours))
        components.append(Component(area=area, perimeter=perimeter, centroid=centroid, bbox=bbox))

    return components


def sobel_edges(gray: np.ndarray) -> np.ndarray:
    """Compute edge magnitude using Sobel operator (OpenCV optimized).

    This replaces the previous manual convolution implementation with OpenCV's
    optimized Sobel function, providing 50-100x speedup.

    Args:
        gray: Grayscale image (2D array)

    Returns:
        Edge magnitude (gradient magnitude)
    """
    import cv2

    # Compute gradients in x and y directions using Sobel operator
    # cv2.CV_32F for float32 output, ksize=3 for 3x3 kernel
    grad_x = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)

    # Compute gradient magnitude
    magnitude = cv2.magnitude(grad_x, grad_y)

    return magnitude


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        intersects = (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
        if intersects:
            inside = not inside
        j = i
    return inside
