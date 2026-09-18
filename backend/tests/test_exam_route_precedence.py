from app.main import app


def test_static_exam_routes_precede_generic_exam_detail_route() -> None:
    paths = list(app.openapi()["paths"])
    detail_index = paths.index("/api/v1/exams/{exam_id}")

    assert paths.index("/api/v1/exams/lead-candidates") < detail_index
    assert paths.index("/api/v1/exams/invigilators/available") < detail_index
