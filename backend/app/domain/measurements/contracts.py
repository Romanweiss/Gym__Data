from dataclasses import dataclass, field


@dataclass(frozen=True)
class MeasurementSubjectRef:
    subject_profile_id: str
    profile_kind: str = "person_placeholder"


@dataclass(frozen=True)
class MeasurementCadencePolicy:
    cadence_days: int = 21
    guidance_notes: tuple[str, ...] = field(
        default_factory=lambda: (
            "Prefer morning measurements under stable conditions.",
            "Prefer fasting or pre-food state where possible.",
            "Prefer taking measurements before training.",
            "Keep conditions comparable across sessions.",
        )
    )


@dataclass(frozen=True)
class MeasurementPhotoRef:
    photo_workflow_enabled: bool = False
    storage_mode: str = "not_implemented_foundation"
