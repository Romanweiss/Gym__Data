CREATE INDEX IF NOT EXISTS idx_workouts_date ON raw.workouts (workout_date DESC);
CREATE INDEX IF NOT EXISTS idx_workouts_quality ON raw.workouts (source_quality);
CREATE INDEX IF NOT EXISTS idx_exercise_instances_workout ON raw.exercise_instances (workout_id);
CREATE INDEX IF NOT EXISTS idx_exercise_instances_canonical ON raw.exercise_instances (exercise_name_canonical);
CREATE INDEX IF NOT EXISTS idx_sets_workout ON raw.sets (workout_id);
CREATE INDEX IF NOT EXISTS idx_cardio_workout ON raw.cardio_segments (workout_id);
CREATE INDEX IF NOT EXISTS idx_recovery_workout ON raw.recovery_events (workout_id);

