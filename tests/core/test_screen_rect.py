import math

import pytest

from ai_translate.core.models import ScreenRect


@pytest.mark.parametrize("field", ["x", "y", "width", "height"])
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_screen_rect_rejects_non_finite_coordinates(field: str, value: float) -> None:
    coordinates = {"x": -100, "y": 20, "width": 80, "height": 40}
    coordinates[field] = value
    assert ScreenRect(**coordinates).is_usable() is False


def test_screen_rect_accepts_negative_origin_and_reverse_drag() -> None:
    rect = ScreenRect(x=-100, y=20, width=-80, height=-40)
    assert rect.is_usable() is True
    assert rect.canonical() == ScreenRect(x=-180, y=-20, width=80, height=40)


def test_screen_rect_rejects_overflow_when_canonicalizing() -> None:
    rect = ScreenRect(x=-1.7e308, y=20, width=-1.7e308, height=40)
    assert rect.is_usable() is False
