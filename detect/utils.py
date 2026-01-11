from __future__ import annotations

from collections import deque
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


def connected_components(mask: np.ndarray) -> list[Component]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[Component] = []

    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue
            queue = deque([(y, x)])
            visited[y, x] = True
            area = 0
            perimeter = 0
            sum_y = 0
            sum_x = 0
            min_x = max_x = x
            min_y = max_y = y

            while queue:
                cy, cx = queue.popleft()
                area += 1
                sum_y += cy
                sum_x += cx
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)

                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < height and 0 <= nx < width:
                        if mask[ny, nx]:
                            if not visited[ny, nx]:
                                visited[ny, nx] = True
                                queue.append((ny, nx))
                        else:
                            perimeter += 1
                    else:
                        perimeter += 1

            centroid = (sum_x / area, sum_y / area)
            bbox = (min_x, min_y, max_x, max_y)
            components.append(
                Component(area=area, perimeter=perimeter, centroid=centroid, bbox=bbox)
            )
    return components


def sobel_edges(gray: np.ndarray) -> np.ndarray:
    kernel_x = np.array([[1, 0, -1], [2, 0, -2], [1, 0, -1]], dtype=np.float32)
    kernel_y = np.array([[1, 2, 1], [0, 0, 0], [-1, -2, -1]], dtype=np.float32)
    padded = np.pad(gray, 1, mode="edge")
    gx = np.zeros_like(gray, dtype=np.float32)
    gy = np.zeros_like(gray, dtype=np.float32)
    height, width = gray.shape

    for y in range(height):
        for x in range(width):
            window = padded[y : y + 3, x : x + 3]
            gx[y, x] = np.sum(window * kernel_x)
            gy[y, x] = np.sum(window * kernel_y)

    return np.hypot(gx, gy)


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
