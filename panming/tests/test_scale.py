"""Small synthetic load probe, not a production load or browser performance claim."""

import json
from time import perf_counter

from test_workflow import client as client

from panming.app import Capture, ReportRequest, build_report, capture_material, today


def test_bootstrap_at_250_materials(client):
    store = client.app.state.store
    body = "Synthetic database research evidence for the scale probe. " * 36
    start = perf_counter()
    with store.transaction() as conn:
        for index in range(250):
            capture_material(store, conn, Capture(title=f"scale-only-{index}", content=body))
        from datetime import date

        build_report(store, conn, ReportRequest(date=date.fromisoformat(today())))
    import_ms = (perf_counter() - start) * 1000
    start = perf_counter()
    response = client.get("/api/v1/bootstrap")
    read_ms = (perf_counter() - start) * 1000
    assert response.status_code == 200
    assert len(response.json()["materials"]) == 250
    assert len(response.json()["reports"][0]["sources"]) == 250
    print(
        json.dumps(
            {
                "materials": 250,
                "characters_per_source": len(body),
                "capture_and_report_ms": round(import_ms, 1),
                "bootstrap_ms": round(read_ms, 1),
                "response_bytes": len(response.content),
            },
            ensure_ascii=False,
        )
    )
