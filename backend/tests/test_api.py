from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import create_app


class FakePostgresClient:
    def fetch_one(self, query: str, params=None):
        if "FROM raw.workouts" in query and "WHERE workout_id" in query:
            if params["workout_id"] != "2026-03-08":
                return None
            return {
                "workout_id": "2026-03-08",
                "workout_date": date(2026, 3, 8),
                "session_sequence": 1,
                "title_raw": "Ноги, Трицепс, Плечи",
                "split_raw": ["Ноги", "Трицепс", "Плечи"],
                "split_normalized": ["legs", "triceps", "shoulders"],
                "source_type": "manual_log",
                "source_quality": "raw_detailed",
                "source_text": "sample source",
                "notes": None,
            }
        return None

    def fetch_all(self, query: str, params=None):
        if "FROM raw.cardio_segments" in query:
            return [
                {
                    "segment_order": 1,
                    "machine": "эллиптический тренажёр",
                    "direction": "forward",
                    "duration_min": 6,
                    "notes": None,
                }
            ]
        if "FROM raw.recovery_events" in query:
            return [
                {
                    "event_order": 1,
                    "event_type": "stretching",
                    "duration_min": 20,
                    "notes": None,
                }
            ]
        if "FROM raw.exercise_instances" in query:
            return [
                {
                    "exercise_instance_id": "2026-03-08_ex_01",
                    "workout_id": "2026-03-08",
                    "exercise_order": Decimal("3"),
                    "exercise_name_raw": "Приседания со штангой",
                    "exercise_name_canonical": "приседания со штангой",
                    "category": "strength",
                    "load_type": "barbell",
                    "bodyweight": False,
                    "attributes": {},
                    "raw_sets_text": "20х14, 20х15, 60х10, 80х8, 100х7, 120х4, 120х5, 125х",
                    "notes": None,
                    "source_quality": "raw_detailed",
                },
                {
                    "exercise_instance_id": "2026-03-08_ex_02",
                    "workout_id": "2026-03-08",
                    "exercise_order": Decimal("4"),
                    "exercise_name_raw": "Скручивания",
                    "exercise_name_canonical": "скручивания",
                    "category": "strength",
                    "load_type": "bodyweight",
                    "bodyweight": True,
                    "attributes": {},
                    "raw_sets_text": "12, 13",
                    "notes": None,
                    "source_quality": "raw_detailed",
                },
            ]
        if "FROM raw.sets" in query:
            return [
                {
                    "exercise_instance_id": "2026-03-08_ex_01",
                    "set_order": 8,
                    "weight_kg": Decimal("125"),
                    "reps": 1,
                    "raw_value": "125х",
                    "parse_note": "reps_missing_defaulted_to_1",
                },
                {
                    "exercise_instance_id": "2026-03-08_ex_02",
                    "set_order": 1,
                    "weight_kg": Decimal("0"),
                    "reps": 12,
                    "raw_value": "12",
                    "parse_note": None,
                },
            ]
        return []


def test_workout_detail_endpoint_returns_full_nested_structure(monkeypatch) -> None:
    from app.services import workout_service

    monkeypatch.setattr(workout_service, "get_postgres_client", lambda: FakePostgresClient())

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/workouts/2026-03-08")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workout_id"] == "2026-03-08"
    assert payload["source_quality"] == "raw_detailed"
    assert payload["cardio_segments"][0]["order"] == 1
    assert payload["recovery_events"][0]["event_type"] == "stretching"
    assert payload["exercise_instances"][0]["exercise_instance_id"] == "2026-03-08_ex_01"
    assert payload["exercise_instances"][0]["display_order"] == 1
    assert payload["exercise_instances"][0]["sets"][0]["parse_note"] == "reps_missing_defaulted_to_1"
    assert payload["exercise_instances"][1]["bodyweight"] is True
    assert payload["exercise_instances"][1]["sets"][0]["weight_kg"] == 0.0
