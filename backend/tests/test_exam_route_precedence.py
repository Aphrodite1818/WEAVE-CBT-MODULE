from app.main import app


def _route_index(path: str, method: str = "GET") -> int:
    method = method.upper()
    for index, route in enumerate(app.routes):
        methods = getattr(route, "methods", set()) or set()
        if getattr(route, "path", None) == path and method in methods:
            return index
    raise AssertionError(f"Route {method} {path} was not registered")


def test_static_exam_routes_precede_generic_exam_detail_route() -> None:
    detail_index = _route_index("/api/v1/exams/{exam_id}")

    assert _route_index("/api/v1/exams/lead-candidates") < detail_index
    assert _route_index("/api/v1/exams/invigilators/available") < detail_index
