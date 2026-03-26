from app.db.clickhouse import get_clickhouse_client
from app.db.postgres import get_postgres_client


def get_health_report() -> dict[str, object]:
    components: dict[str, dict[str, object]] = {}
    overall_status = "ok"

    postgres_client = get_postgres_client()
    clickhouse_client = get_clickhouse_client()

    try:
        components["postgres"] = {"status": "ok", "reachable": postgres_client.ping()}
    except Exception as exc:  # pragma: no cover - defensive health path
        components["postgres"] = {"status": "error", "detail": str(exc)}
        overall_status = "degraded"

    try:
        components["clickhouse"] = {"status": "ok", "reachable": clickhouse_client.ping()}
    except Exception as exc:  # pragma: no cover - defensive health path
        components["clickhouse"] = {"status": "error", "detail": str(exc)}
        overall_status = "degraded"

    if not all(component.get("reachable", False) for component in components.values() if component["status"] == "ok"):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "service": "backend",
        "components": components,
    }

