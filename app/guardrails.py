
from __future__ import annotations

import math
from typing import Any

from .schemas import DirectiveInterpretation, OptimizeRequest


ALLOWED_TYPES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _validate_hours(value: Any) -> list[int]:
    if not isinstance(value, list):
        raise ValueError("hours must be an array")
    if any(isinstance(h, bool) or not isinstance(h, int) for h in value):
        raise ValueError("hours must contain integers only")
    if any(h < 0 or h > 23 for h in value):
        raise ValueError("hours must be between 0 and 23")
    if value != sorted(set(value)):
        raise ValueError("hours must be unique and in ascending order")
    return value


def validate_llm_directives(
    req: OptimizeRequest, raw: list[dict[str, Any]]
) -> list[DirectiveInterpretation]:
    if len(raw) != len(req.operator_notes):
        raise ValueError("LLM must return exactly one directive per operator note")

    validated: list[DirectiveInterpretation] = []

    for expected_index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError("Each directive must be a JSON object")

        if item.get("note_index") != expected_index:
            raise ValueError("note_index mapping/order is invalid")

        directive_type = item.get("directive_type")
        if directive_type not in ALLOWED_TYPES:
            raise ValueError("Unsupported directive_type")

        applies = item.get("applies")
        if not isinstance(applies, bool):
            raise ValueError("applies must be boolean")

        adjustment = item.get("structured_adjustment")
        explanation = item.get("explanation", "")
        if not isinstance(explanation, str):
            raise ValueError("explanation must be a string")

        if directive_type == "no_op":
            if applies is not False or adjustment is not None:
                raise ValueError(
                    "no_op requires applies=false and structured_adjustment=null"
                )
        else:
            if applies is not True:
                raise ValueError("Every non-no_op directive requires applies=true")
            if not isinstance(adjustment, dict):
                raise ValueError("structured_adjustment must be an object")

            if directive_type in {"no_charge_window", "no_discharge_window"}:
                if set(adjustment.keys()) != {"hours"}:
                    raise ValueError("Invalid structured_adjustment shape")
                _validate_hours(adjustment["hours"])

            elif directive_type == "solar_reduction":
                if set(adjustment.keys()) != {"hours", "factor"}:
                    raise ValueError("Invalid structured_adjustment shape")
                _validate_hours(adjustment["hours"])
                factor = _finite_number(adjustment["factor"], "factor")
                if not 0 <= factor <= 1:
                    raise ValueError("solar_reduction factor must be in [0,1]")
                adjustment["factor"] = factor

            elif directive_type == "minimum_battery_reserve":
                if set(adjustment.keys()) != {"hours", "minimum_energy_kwh"}:
                    raise ValueError("Invalid structured_adjustment shape")
                _validate_hours(adjustment["hours"])
                reserve = _finite_number(
                    adjustment["minimum_energy_kwh"], "minimum_energy_kwh"
                )
                if reserve < 0 or reserve > req.battery.capacity_kwh:
                    raise ValueError(
                        "minimum_energy_kwh must be within battery capacity"
                    )
                adjustment["minimum_energy_kwh"] = reserve

            elif directive_type == "max_grid_window":
                if set(adjustment.keys()) != {"hours", "max_grid_kwh"}:
                    raise ValueError("Invalid structured_adjustment shape")
                _validate_hours(adjustment["hours"])
                cap = _finite_number(adjustment["max_grid_kwh"], "max_grid_kwh")
                if cap < 0:
                    raise ValueError("max_grid_kwh must be non-negative")
                adjustment["max_grid_kwh"] = cap

        validated.append(
            DirectiveInterpretation(
                note_index=expected_index,
                applies=applies,
                directive_type=directive_type,
                structured_adjustment=adjustment,
                explanation=explanation.strip(),
            )
        )

    return validated
