"""
SafeVision AI — Geometry Utilities

Provides geometric algorithms for computer vision spatial operations:
- Centroid calculation from bounding boxes
- Point-in-polygon test (ray casting algorithm) for zone incursion detection
- Bounding box IoU (Intersection over Union) for spatial PPE association
"""


def calculate_centroid(bbox: list[float] | tuple[float, float, float, float]) -> tuple[float, float]:
    """
    Calculate the (x, y) centroid coordinates from a bounding box.

    Bbox format: [x1, y1, x2, y2]
    Returns: (centroid_x, centroid_y)
    """
    if len(bbox) < 4:
        raise ValueError(f"Invalid bbox format: expected at least 4 values [x1, y1, x2, y2], got {bbox}")

    x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
    centroid_x = (x1 + x2) / 2.0
    centroid_y = (y1 + y2) / 2.0
    return (centroid_x, centroid_y)


def bbox_contains(outer: list[float], inner: list[float]) -> bool:
    """
    Check if the inner bounding box centroid falls within the outer bounding box.

    This is the deterministic spatial test for PPE→person association when
    track_id is unavailable: a PPE item (helmet, vest) should be spatially
    contained within or overlapping the person bounding box it belongs to.

    Args:
        outer: Person bounding box [x1, y1, x2, y2]
        inner: PPE item bounding box [x1, y1, x2, y2]

    Returns:
        True if the inner bbox centroid falls within the outer bbox.
    """
    if not outer or len(outer) < 4 or not inner or len(inner) < 4:
        return False

    ox1, oy1, ox2, oy2 = float(outer[0]), float(outer[1]), float(outer[2]), float(outer[3])
    # Use centroid of PPE bbox
    icx = (float(inner[0]) + float(inner[2])) / 2.0
    icy = (float(inner[1]) + float(inner[3])) / 2.0

    return ox1 <= icx <= ox2 and oy1 <= icy <= oy2


def point_in_polygon(
    point: tuple[float, float] | list[float],
    polygon: list[list[float]] | list[tuple[float, float]],
) -> bool:
    """
    Determine if a point (x, y) is inside a polygon using the Ray-Casting algorithm.

    Compatible with normalized coordinates (0.0-1.0) and pixel coordinates.
    Works for both convex and non-convex polygons.

    Args:
        point: (x, y) coordinate
        polygon: List of polygon vertices [[x1, y1], [x2, y2], ...]

    Returns:
        True if point is strictly or conditionally inside polygon, False otherwise.
    """
    if not polygon or len(polygon) < 3:
        # A polygon must have at least 3 vertices
        return False

    px, py = float(point[0]), float(point[1])
    n = len(polygon)
    inside = False

    p1x, p1y = float(polygon[0][0]), float(polygon[0][1])

    for i in range(1, n + 1):
        p2x, p2y = float(polygon[i % n][0]), float(polygon[i % n][1])

        # Check ray intersection
        if py > min(p1y, p2y):
            if py <= max(p1y, p2y):
                if px <= max(p1x, p2x):
                    if p1y != p2y:
                        x_inters = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    else:
                        x_inters = p1x

                    if p1x == p2x or px <= x_inters:
                        inside = not inside

        p1x, p1y = p2x, p2y

    return inside
