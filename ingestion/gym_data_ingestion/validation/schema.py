import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

from gym_data_ingestion.models import DatasetValidationError


@lru_cache
def get_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def validate_document(payload: dict, schema_path: Path) -> None:
    validator = get_validator(schema_path)
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        first_error = errors[0]
        location = ".".join(str(part) for part in first_error.path) or "<root>"
        raise DatasetValidationError(f"Schema validation failed at {location}: {first_error.message}")
