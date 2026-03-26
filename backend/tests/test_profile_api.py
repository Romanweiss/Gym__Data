from fastapi.testclient import TestClient

from app.main import create_app


def test_profile_overview_endpoint_returns_workspace_payload(monkeypatch) -> None:
    from app.api.routes import profile as profile_route

    monkeypatch.setattr(
        profile_route,
        "get_current_profile_overview",
        lambda: {
            "subject_profile": {"subject_profile_id": "subject_default"},
            "latest_workout": {"workout_id": "2026-03-25", "workout_date": "2026-03-25"},
            "latest_measurement": {
                "measurement_session_id": "2026-03-01_morning",
                "measured_date": "2026-03-01",
            },
            "latest_measurements": [],
            "measurement_overdue": {"recommended_now": True},
            "weekly_workout_load_snapshot": {"week_start": "2026-03-23"},
            "recent_weekly_workout_load": [],
            "cardio_summary": {"latest_week_start": "2026-03-23", "items": []},
            "recovery_summary": {"latest_week_start": "2026-03-23", "items": []},
            "recent_workouts": [],
            "recent_measurements": [],
        },
    )

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/profile/current/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject_profile"]["subject_profile_id"] == "subject_default"
    assert payload["latest_workout"]["workout_id"] == "2026-03-25"


def test_profile_timeline_endpoint_returns_combined_feed(monkeypatch) -> None:
    from app.api.routes import profile as profile_route

    monkeypatch.setattr(
        profile_route,
        "get_current_profile_timeline",
        lambda **kwargs: {
            "subject_profile_id": "subject_default",
            "filters": kwargs,
            "items": [
                {
                    "event_type": "measurement_session",
                    "event_id": "2026-03-01_morning",
                    "event_date": "2026-03-01",
                },
                {
                    "event_type": "workout",
                    "event_id": "2026-02-27",
                    "event_date": "2026-02-27",
                },
            ],
        },
    )

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/profile/current/timeline?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["event_type"] == "measurement_session"
    assert payload["items"][1]["event_type"] == "workout"


def test_profile_progress_highlights_endpoint_returns_measurement_highlights(monkeypatch) -> None:
    from app.api.routes import profile as profile_route

    monkeypatch.setattr(
        profile_route,
        "get_current_profile_progress_highlights",
        lambda: {
            "subject_profile_id": "subject_default",
            "measurement_highlights": {
                "body_weight": {"latest_value_numeric": 92.6, "delta_value_numeric": -0.6},
                "waist": {"latest_value_numeric": 92.9, "delta_value_numeric": -0.9},
                "chest": {"latest_value_numeric": 108.6, "delta_value_numeric": 0.4},
                "biceps": {"latest_value_numeric": 37.8, "delta_value_numeric": 0.3},
            },
            "last_workout": {"workout_id": "2026-03-25"},
            "last_workout_summary": {"set_count": 18},
            "recent_workouts": [],
            "measurement_overdue": {"recommended_now": True},
        },
    )

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/profile/current/progress-highlights")

    assert response.status_code == 200
    payload = response.json()
    assert payload["measurement_highlights"]["body_weight"]["latest_value_numeric"] == 92.6
    assert payload["last_workout"]["workout_id"] == "2026-03-25"
