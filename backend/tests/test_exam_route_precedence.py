from collections.abc import Callable

from app.domains.exams.read_router import get_exam
from app.domains.exams.router import (
    list_available_invigilators,
    list_eligible_lead_teachers,
)
from app.main import app


def _route_index(endpoint: Callable, method: str = "GET") -> int:
    method = method.upper()
    for index, route in enumerate(app.routes):
        methods = getattr(route, "methods", set()) or set()
        if getattr(route, "endpoint", None) is endpoint and method in methods:
            return index
    raise AssertionError(
        f"Route {method} for endpoint {endpoint.__name__} was not registered"
    )


def test_static_exam_routes_precede_generic_exam_detail_route() -> None:
    detail_index = _route_index(get_exam)

    assert _route_index(list_eligible_lead_teachers) < detail_index
    assert _route_index(list_available_invigilators) < detail_index
