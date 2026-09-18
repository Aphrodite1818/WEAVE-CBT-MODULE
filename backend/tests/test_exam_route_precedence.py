from app.main import app


def _route_index(route_name: str, method: str = "GET") -> int:
    method = method.upper()
    for index, route in enumerate(app.routes):
        methods = getattr(route, "methods", set()) or set()
        if getattr(route, "name", None) == route_name and method in methods:
            return index
    raise AssertionError(f"Route {method} {route_name} was not registered")


def test_static_exam_routes_precede_generic_exam_detail_route() -> None:
    detail_index = _route_index("get_exam")

    assert _route_index("list_eligible_lead_teachers") < detail_index
    assert _route_index("list_available_invigilators") < detail_index
