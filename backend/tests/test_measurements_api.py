from datetime import date, datetime

from fastapi.testclient import TestClient

from app.main import create_app


class FakeMeasurementPostgresClient:
    def fetch_one(self, query: str, params=None):
        if "FROM raw.body_measurement_sessions s" in query and "WHERE s.measurement_session_id" in query:
            if params["measurement_session_id"] != "2026-03-01_morning":
                return None
            return {
                "measurement_session_id": "2026-03-01_morning",
                "subject_profile_id": "subject_default",
                "profile_kind": "person_placeholder",
                "display_name": "Default single-user profile",
                "is_default": True,
                "measured_at": datetime(2026, 3, 1, 8, 0, 0),
                "measured_date": date(2026, 3, 1),
                "source_type": "manual_entry",
                "source_quality": "measured_direct",
                "context_time_of_day": "morning",
                "fasting_state": True,
                "before_training": True,
                "notes": "Latest recorded session before a longer measurement gap.",
            }
        if "FROM raw.body_measurement_sessions" in query and "ORDER BY measured_at DESC" in query:
            return {
                "measurement_session_id": "2026-03-01_morning",
                "subject_profile_id": "subject_default",
                "measured_at": datetime(2026, 3, 1, 8, 0, 0),
                "measured_date": date(2026, 3, 1),
            }
        if "COUNT(*)::int AS workouts_since_last_measurement" in query:
            return {
                "workouts_since_last_measurement": 8,
                "last_workout_date": date(2026, 3, 25),
            }
        if "COUNT(*)::int AS workouts_total" in query:
            return {"workouts_total": 43}
        return None

    def fetch_all(self, query: str, params=None):
        if "FROM raw.body_measurement_values v" in query:
            return [
                {
                    "measurement_value_id": "2026-03-01_morning_mv_04",
                    "measurement_type_canonical": "waist",
                    "measurement_type_raw": "талия",
                    "value_numeric": 92.9,
                    "unit": "cm",
                    "side_or_scope": None,
                    "raw_value": "92.9 см",
                    "parse_note": None,
                    "notes": None,
                    "order_in_session": 4,
                    "category": "core",
                    "value_kind": "circumference",
                    "sort_order": 4,
                },
                {
                    "measurement_value_id": "2026-03-01_morning_mv_10",
                    "measurement_type_canonical": "body_weight",
                    "measurement_type_raw": "вес",
                    "value_numeric": 92.6,
                    "unit": "kg",
                    "side_or_scope": None,
                    "raw_value": "92.6 кг",
                    "parse_note": None,
                    "notes": None,
                    "order_in_session": 10,
                    "category": "body_mass",
                    "value_kind": "weight",
                    "sort_order": 10,
                },
            ]
        if "FROM raw.body_measurement_sessions s" in query and "LEFT JOIN" in query:
            return [
                {
                    "measurement_session_id": "2026-03-01_morning",
                    "subject_profile_id": "subject_default",
                    "measured_at": datetime(2026, 3, 1, 8, 0, 0),
                    "measured_date": date(2026, 3, 1),
                    "source_type": "manual_entry",
                    "source_quality": "measured_direct",
                    "context_time_of_day": "morning",
                    "fasting_state": True,
                    "before_training": True,
                    "notes": "Latest recorded session before a longer measurement gap.",
                    "measurement_value_count": 10,
                    "body_weight_value": 92.6,
                    "body_weight_unit": "kg",
                }
            ]
        return []


class FakeMeasurementClickHouseClient:
    def fetch_all(self, query: str, params=None):
        if "FROM gym_data_mart.mart_measurement_latest" in query:
            return [
                {
                    "subject_profile_id": "subject_default",
                    "measurement_type_canonical": "waist",
                    "category": "core",
                    "value_kind": "circumference",
                    "sort_order": 4,
                    "unit": "cm",
                    "latest_measurement_session_id": "2026-03-01_morning",
                    "latest_measured_at": datetime(2026, 3, 1, 8, 0, 0),
                    "latest_measured_date": date(2026, 3, 1),
                    "latest_value_numeric": 92.9,
                    "previous_measurement_session_id": "2026-02-22_morning",
                    "previous_measured_date": date(2026, 2, 22),
                    "previous_value_numeric": 93.8,
                    "delta_value_numeric": -0.9,
                    "days_since_previous": 7,
                }
            ]
        if "FROM gym_data_mart.mart_measurement_progress" in query:
            return [
                {
                    "subject_profile_id": "subject_default",
                    "measurement_session_id": "2026-03-01_morning",
                    "measured_at": datetime(2026, 3, 1, 8, 0, 0),
                    "measured_date": date(2026, 3, 1),
                    "measurement_type_canonical": "waist",
                    "measurement_type_raw": "талия",
                    "category": "core",
                    "value_kind": "circumference",
                    "sort_order": 4,
                    "unit": "cm",
                    "side_or_scope": None,
                    "source_quality": "measured_direct",
                    "context_time_of_day": "morning",
                    "value_numeric": 92.9,
                    "previous_measurement_session_id": "2026-02-22_morning",
                    "previous_measured_date": date(2026, 2, 22),
                    "previous_value_numeric": 93.8,
                    "delta_value_numeric": -0.9,
                    "days_since_previous": 7,
                    "workouts_since_previous_measurement": 4,
                    "total_sets_since_previous_measurement": 20,
                    "total_reps_since_previous_measurement": 224,
                    "total_volume_kg_since_previous_measurement": 7425.0,
                    "cardio_minutes_since_previous_measurement": 55,
                    "recovery_minutes_since_previous_measurement": 0,
                }
            ]
        return []


def test_measurement_detail_endpoint_returns_session_structure(monkeypatch) -> None:
    from app.services import measurement_service

    monkeypatch.setattr(
        measurement_service,
        "get_postgres_client",
        lambda: FakeMeasurementPostgresClient(),
    )

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/measurements/2026-03-01_morning")

    assert response.status_code == 200
    payload = response.json()
    assert payload["measurement_session_id"] == "2026-03-01_morning"
    assert payload["subject_profile"]["subject_profile_id"] == "subject_default"
    assert payload["measurements"][0]["measurement_type_canonical"] == "waist"
    assert payload["measurements"][1]["measurement_type_canonical"] == "body_weight"


def test_measurements_latest_endpoint_returns_latest_values(monkeypatch) -> None:
    from app.services import measurement_service

    monkeypatch.setattr(
        measurement_service,
        "get_clickhouse_client",
        lambda: FakeMeasurementClickHouseClient(),
    )

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/measurements/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject_profile_id"] == "subject_default"
    assert payload["items"][0]["measurement_type_canonical"] == "waist"
    assert payload["items"][0]["delta_value_numeric"] == -0.9


def test_measurements_progress_endpoint_returns_timeline(monkeypatch) -> None:
    from app.services import measurement_service

    monkeypatch.setattr(
        measurement_service,
        "get_clickhouse_client",
        lambda: FakeMeasurementClickHouseClient(),
    )

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/measurements/progress?measurement_type=waist")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filters"]["measurement_type"] == "waist"
    assert payload["items"][0]["workouts_since_previous_measurement"] == 4
    assert payload["items"][0]["delta_value_numeric"] == -0.9


def test_measurements_overdue_endpoint_returns_recommendation(monkeypatch) -> None:
    from app.services import measurement_service

    class FakeDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 3, 26)

    monkeypatch.setattr(
        measurement_service,
        "get_postgres_client",
        lambda: FakeMeasurementPostgresClient(),
    )
    monkeypatch.setattr(measurement_service, "date", FakeDate)

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/measurements/overdue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["last_measurement_session_id"] == "2026-03-01_morning"
    assert payload["workouts_since_last_measurement"] == 8
    assert payload["recommended_now"] is True
