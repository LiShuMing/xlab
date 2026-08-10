"""Flask application for the LongCycle product prototype."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

from cycle_lab.config import integration_snapshot
from cycle_lab.data import store
from cycle_lab.integrations.llm import generate_market_brief


PACKAGE_DIR = Path(__file__).resolve().parent
UI_DIR = PACKAGE_DIR / "ui"


def create_app() -> Flask:
    store.init_db()
    app = Flask(
        __name__,
        template_folder=str(UI_DIR / "templates"),
        static_folder=str(UI_DIR / "static"),
        static_url_path="/static",
    )

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/dashboard")
    def dashboard() -> Any:
        return jsonify(store.product_dashboard())

    @app.get("/api/integrations")
    def integrations() -> Any:
        probe = request.args.get("probe", "1") != "0"
        return jsonify(integration_snapshot(probe_psql=probe))

    @app.post("/api/data/refresh")
    def refresh_data() -> Any:
        payload = request.get_json(silent=True) or {}
        return jsonify(store.refresh_real_data(start_date=payload.get("start_date", "20100101")))

    @app.post("/api/insight")
    def insight() -> Any:
        payload = request.get_json(silent=True) or store.product_dashboard()
        result = generate_market_brief(payload)
        if result.get("ok"):
            store.save_brief("LLM 市场状态简报", result["content"], "llm")
        return jsonify(result)

    @app.get("/api/watchlist")
    def list_watchlist() -> Any:
        return jsonify(store.list_hypotheses())

    @app.post("/api/watchlist")
    def create_watchlist_item() -> Any:
        payload = request.get_json(force=True)
        return jsonify(store.upsert_hypothesis(payload)), 201

    @app.put("/api/watchlist/<hypothesis_id>")
    def update_watchlist_item(hypothesis_id: str) -> Any:
        payload = request.get_json(force=True)
        payload["hypothesis_id"] = hypothesis_id
        return jsonify(store.upsert_hypothesis(payload))

    @app.delete("/api/watchlist/<hypothesis_id>")
    def delete_watchlist_item(hypothesis_id: str) -> Any:
        store.delete_hypothesis(hypothesis_id)
        return jsonify({"ok": True})

    @app.post("/api/watchlist/<hypothesis_id>/snapshots")
    def create_evidence_snapshot(hypothesis_id: str) -> Any:
        payload = request.get_json(silent=True) or {}
        return jsonify(store.create_snapshot(hypothesis_id, payload.get("note", ""))), 201

    @app.get("/api/snapshots")
    def list_snapshots() -> Any:
        return jsonify(store.list_snapshots(request.args.get("hypothesis_id")))

    @app.get("/api/experiments")
    def list_experiments() -> Any:
        return jsonify(store.list_experiments())

    @app.post("/api/experiments")
    def create_experiment() -> Any:
        return jsonify(store.create_experiment(request.get_json(force=True))), 201

    @app.get("/api/briefs")
    def list_briefs() -> Any:
        return jsonify(store.list_briefs())

    @app.get("/api/reviews")
    def list_reviews() -> Any:
        return jsonify(store.list_monthly_reviews())

    @app.post("/api/reviews")
    def create_review() -> Any:
        return jsonify(store.create_monthly_review(request.get_json(force=True))), 201

    return app


app = create_app()
