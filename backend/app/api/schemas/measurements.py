from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MeasurementValueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement_type: str = Field(min_length=1)
    value_numeric: float = Field(gt=0)
    unit: str | None = None
    side_or_scope: str | None = None
    raw_value: str | None = None
    notes: str | None = None


class MeasurementSessionUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement_session_id: str | None = None
    subject_profile_id: str | None = None
    measured_at: datetime
    measured_date: date | None = None
    source_type: str = "manual_entry"
    source_quality: Literal["measured_direct", "self_reported", "imported_record"] = (
        "measured_direct"
    )
    context_time_of_day: Literal["morning", "unknown", "other"] = "unknown"
    fasting_state: bool | None = None
    before_training: bool | None = None
    notes: str | None = None
    measurements: list[MeasurementValueInput] = Field(min_length=1)

    @model_validator(mode="after")
    def measured_date_matches_measured_at(self) -> "MeasurementSessionUpsertRequest":
        if self.measured_date and self.measured_date != self.measured_at.date():
            raise ValueError("measured_date must match the date part of measured_at.")
        return self


class SubjectProfileResponse(BaseModel):
    subject_profile_id: str
    profile_kind: str
    display_name: str
    is_default: bool


class MeasurementValueResponse(BaseModel):
    measurement_value_id: str
    measurement_type_canonical: str
    measurement_type_raw: str
    value_numeric: float
    unit: str
    side_or_scope: str | None = None
    raw_value: str | None = None
    parse_note: str | None = None
    notes: str | None = None
    order_in_session: int
    category: str
    value_kind: str
    sort_order: int


class MeasurementSessionDetailResponse(BaseModel):
    measurement_session_id: str
    subject_profile: SubjectProfileResponse
    measured_at: str
    measured_date: str
    source_type: str | None = None
    source_quality: str
    context_time_of_day: str
    fasting_state: bool | None = None
    before_training: bool | None = None
    notes: str | None = None
    measurements: list[MeasurementValueResponse]


class MeasurementRefreshResponse(BaseModel):
    run_id: str
    source_file_count: int
    postgres_counts: dict[str, int]
    clickhouse_counts: dict[str, int]


class MeasurementMutationResponse(BaseModel):
    status: Literal["created", "updated"]
    measurement_session: MeasurementSessionDetailResponse
    refresh: MeasurementRefreshResponse
