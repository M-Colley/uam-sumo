import math
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from createUamHubs import get_orthogonal_points


def test_get_orthogonal_points_handles_single_coordinate():
    centre = (0.0, 0.0)
    point = (0.0, 0.0)
    distance = 10.0

    first, second = get_orthogonal_points(centre, point, distance)

    # With a single point the orthogonal points should be placed directly above and below the
    # original coordinate at the requested distance.
    assert math.isclose(first[0], point[0])
    assert math.isclose(second[0], point[0])
    assert math.isclose(first[1], point[1] - distance)
    assert math.isclose(second[1], point[1] + distance)


def test_get_orthogonal_points_distance_preserved():
    centre = (1.0, 1.0)
    point = (3.0, 1.0)
    distance = 5.0

    first, second = get_orthogonal_points(centre, point, distance)

    # Both points should be exactly `distance` away from the original point.
    assert math.isclose(math.dist(first, point), distance)
    assert math.isclose(math.dist(second, point), distance)

