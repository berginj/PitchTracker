# generate_marker_spec.py
import json, math
import numpy as np

MM_PER_IN = 25.4

def ball_diameter_mm(ball_type: str) -> float:
    if ball_type == "baseball":
        return 2.90 * MM_PER_IN
    if ball_type == "softball12":  # 12" circumference softball
        circ_in = 12.0
        diam_in = circ_in / math.pi
        return diam_in * MM_PER_IN
    raise ValueError("ball_type must be 'baseball' or 'softball12'")

def fibonacci_markers(holes_total: int, seam_exclusion_deg: float):
    # Matches SCAD logic: z = 1 - 2*(i+0.5)/N, phi = i*golden
    golden_deg = 180.0 * (3.0 - math.sqrt(5.0))
    out = []
    for i in range(holes_total):
        z = 1.0 - 2.0 * (i + 0.5) / holes_total
        lat_deg = math.degrees(math.asin(z))
        if abs(lat_deg) < seam_exclusion_deg:
            continue
        theta = math.acos(z)           # radians
        phi = math.radians(i * golden_deg)
        x = math.sin(theta) * math.cos(phi)
        y = math.sin(theta) * math.sin(phi)
        v = np.array([x, y, z], float)
        v /= np.linalg.norm(v)
        out.append((i, v))
    return out

def index_pair(v, index_sep_mm, radius_mm):
    # Make two points separated along the surface by index_sep_mm (total)
    v = v / np.linalg.norm(v)

    # pick a stable perpendicular axis
    a = np.array([1,0,0], float)
    if abs(np.dot(a, v)) > 0.9:
        a = np.array([0,1,0], float)
    axis = np.cross(v, a); axis /= np.linalg.norm(axis)

    # separation s = r * angle => angle = s/r ; split half each side
    half_ang = (index_sep_mm / radius_mm) / 2.0  # radians

    def rot(axis, ang):
        K = np.array([[0, -axis[2], axis[1]],
                      [axis[2], 0, -axis[0]],
                      [-axis[1], axis[0], 0]], float)
        I = np.eye(3)
        return I + math.sin(ang)*K + (1-math.cos(ang))*(K@K)

    R1 = rot(axis, +half_ang)
    R2 = rot(axis, -half_ang)
    return (R1 @ v, R2 @ v)

def main():
    ball_type = "baseball"       # "baseball" or "softball12"
    holes_total = 40
    seam_exclusion_deg = 10
    index_i = 0
    index_sep_mm = 6.0

    access_window_d_in = 0.50
    stencil_dot_d_in = 0.30

    diam_mm = ball_diameter_mm(ball_type)
    r_mm = diam_mm / 2.0

    markers = fibonacci_markers(holes_total, seam_exclusion_deg)
    marker_map = {i: v for i, v in markers}

    # choose index anchor vector (fall back if excluded by seam)
    if index_i in marker_map:
        idx_v = marker_map[index_i]
    else:
        idx_v = markers[0][1]

    v1, v2 = index_pair(idx_v, index_sep_mm, r_mm)

    spec = {
        "version": 1,
        "ball": {"type": ball_type, "diameter_mm": round(diam_mm, 3)},
        "pattern": {"type": "fibonacci", "holes_total": holes_total, "seam_exclusion_deg": seam_exclusion_deg},
        "marking": {
            "access_window_d_mm": round(access_window_d_in * MM_PER_IN, 3),
            "stencil_dot_d_mm": round(stencil_dot_d_in * MM_PER_IN, 3),
            "index_type": "double_dot",
            "index_sep_mm": index_sep_mm
        },
        "markers": [{"id": int(i), "type": "dot", "v": [float(x) for x in v]} for i, v in markers],
        "index": {"type": "double_dot", "ids": [int(index_i)], "v1": v1.tolist(), "v2": v2.tolist()}
    }

    with open("marker_spec.json", "w") as f:
        json.dump(spec, f, indent=2)

    print("Wrote marker_spec.json with", len(spec["markers"]), "markers")

if __name__ == "__main__":
    main()
