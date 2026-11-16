"""Fast Python quality checks applied before data is published."""

from __future__ import annotations

from dataclasses import dataclass

from airq.transform import ALLOWED_PARAMETERS


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a validation run."""

    total_rows: int
    invalid_rows: int

    @property
    def invalid_rate(self) -> float:
        if self.total_rows == 0:
            return 0.0
        return self.invalid_rows / self.total_rows


class DataQualityError(ValueError):
    """Raised when a dataset violates a blocking quality rule."""


def validate_observations(observations: list, max_invalid_rate: float = 0.20) -> ValidationResult:
    """Check required fields, ranges, and accepted parameters.

    Empty datasets are blocked because an empty successful API response is not evidence
    that the pipeline is healthy.
    """

    if not observations:
        raise DataQualityError("OpenAQ returned no valid observations")

    invalid_rows = 0
    for observation in observations:
        reasons: list[str] = []
        if not observation.observation_id:
            reasons.append("missing_observation_id")
        if observation.location_id <= 0 or observation.sensor_id <= 0:
            reasons.append("invalid_identifier")
        if not observation.location_name:
            reasons.append("missing_location_name")
        if observation.parameter not in ALLOWED_PARAMETERS:
            reasons.append("unsupported_parameter")
        if observation.value < 0:
            reasons.append("negative_value")
        if observation.measured_at is None:
            reasons.append("missing_measured_at")
        if reasons:
            invalid_rows += 1

    result = ValidationResult(total_rows=len(observations), invalid_rows=invalid_rows)
    if result.invalid_rate > max_invalid_rate:
        raise DataQualityError(
            f"Invalid observation rate {result.invalid_rate:.1%} exceeds "
            f"the limit of {max_invalid_rate:.1%}"
        )
    return result
