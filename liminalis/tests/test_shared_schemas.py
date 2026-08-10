from backend._shared.schemas import page_response


def test_page_response_builds_consistent_shape() -> None:
    response = page_response(items=[1, 2], page=2, per_page=2, total_items=5, marker="ok")

    assert response == {
        "items": [1, 2],
        "page": 2,
        "per_page": 2,
        "total_items": 5,
        "total_pages": 3,
        "has_prev": True,
        "has_next": True,
        "marker": "ok",
    }
