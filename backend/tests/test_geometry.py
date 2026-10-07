"""Geometry unit tests: point-in-polygon, bottom-center, polygon validation."""
import pytest

from app.schemas.zone import ZoneCreate
from app.zone_engine.geometry import bottom_center, point_in_polygon

SQUARE = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]


def test_point_inside_polygon():
    assert point_in_polygon([0.5, 0.5], SQUARE) is True


def test_point_outside_polygon():
    assert point_in_polygon([0.05, 0.5], SQUARE) is False
    assert point_in_polygon([0.5, 0.95], SQUARE) is False
    assert point_in_polygon([1.5, 1.5], SQUARE) is False


def test_point_on_boundary_counts_as_inside():
    assert point_in_polygon([0.1, 0.5], SQUARE) is True  # left edge
    assert point_in_polygon([0.5, 0.1], SQUARE) is True  # top edge
    assert point_in_polygon([0.1, 0.1], SQUARE) is True  # corner


def test_concave_polygon():
    # L-shape: notch cut out of the top-right
    poly = [
        [0.0, 0.0], [1.0, 0.0], [1.0, 0.5],
        [0.5, 0.5], [0.5, 1.0], [0.0, 1.0],
    ]
    assert point_in_polygon([0.25, 0.75], poly) is True
    assert point_in_polygon([0.75, 0.75], poly) is False  # in the notch
    assert point_in_polygon([0.75, 0.25], poly) is True


def test_bottom_center():
    # xyxy -> (x_center, y_bottom)
    assert bottom_center([10, 20, 30, 60]) == [20.0, 60.0]


def test_polygon_validation_accepts_array_form():
    z = ZoneCreate(
        camera_id="00000000-0000-0000-0000-000000000000",
        name="door",
        polygon=[[0.1, 0.2], [0.8, 0.2], [0.8, 0.8], [0.1, 0.8]],
    )
    assert z.polygon == [[0.1, 0.2], [0.8, 0.2], [0.8, 0.8], [0.1, 0.8]]


def test_polygon_validation_accepts_object_form():
    z = ZoneCreate(
        camera_id="00000000-0000-0000-0000-000000000000",
        name="door",
        polygon=[
            {"x": 0.10, "y": 0.20},
            {"x": 0.80, "y": 0.20},
            {"x": 0.80, "y": 0.80},
            {"x": 0.10, "y": 0.80},
        ],
    )
    assert z.polygon[0] == [0.1, 0.2]


def test_polygon_validation_rejects_too_few_points():
    with pytest.raises(Exception):
        ZoneCreate(
            camera_id="00000000-0000-0000-0000-000000000000",
            name="bad",
            polygon=[[0.1, 0.1], [0.9, 0.9]],
        )


def test_polygon_validation_rejects_denormalized_coords():
    with pytest.raises(Exception):
        ZoneCreate(
            camera_id="00000000-0000-0000-0000-000000000000",
            name="bad",
            polygon=[[0.1, 0.1], [1.5, 0.1], [0.5, 0.9]],
        )
    with pytest.raises(Exception):
        ZoneCreate(
            camera_id="00000000-0000-0000-0000-000000000000",
            name="bad",
            polygon=[[0.1, 0.1], [-0.2, 0.1], [0.5, 0.9]],
        )
