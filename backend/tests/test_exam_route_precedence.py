from starlette.routing import Match

from app.main import app


def _first_full_match_name(path: str, method: str = "GET") -> str:
    scope = {
        "type": "http",
        "path": path,
        "method": method.upper(),
        "root_path": "",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "headers": [],
        "query_string": b"",
    }

    for route in app.routes:
        match, _ = route.matches(scope)
        if match == Match.FULL:
            endpoint = getattr(route, "endpoint", None)
            endpoint_name = getattr(endpoint, "__name__", None)
            if endpoint_name is not None:
                return endpoint_name
            return getattr(route, "name", "")

    raise AssertionError(f"No route matched {method.upper()} {path}")


def test_static_exam_routes_precede_generic_exam_detail_route() -> None:
    assert (
        _first_full_match_name("/api/v1/exams/lead-candidates")
        == "list_eligible_lead_teachers"
    )
    assert (
        _first_full_match_name("/api/v1/exams/invigilators/available")
        == "list_available_invigilators"
    )
