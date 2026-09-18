from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from dotenv import load_dotenv

from .schemas import OptimizeRequest


# Load variables from .env
load_dotenv()


SYSTEM_PROMPT = """
You are the operator-note interpreter for the GridWise energy optimization API.

You MUST interpret each operator note into exactly one supported directive:

- solar_reduction
- minimum_battery_reserve
- no_charge_window
- no_discharge_window
- max_grid_window
- no_op

Rules:

1) Return exactly one result for every note, preserving note_index order 0..N-1.

2) no_op must use:
   applies = false
   structured_adjustment = null

3) Every non-no_op directive must use:
   applies = true

4) All hours must be unique integers from 0 through 23
   and returned in ascending order.

5) Time windows are start-inclusive and end-exclusive.
   Example:
   1 PM to 3 PM -> [13, 14]

6) For solar_reduction, factor means the usable fraction REMAINING.
   Example:
   80% reduction -> factor = 0.2

7) Never invent:
   - demand
   - tariff
   - battery parameters
   - unsupported directive types
   - unsupported hours
   - unsupported numeric values

8) If a note does not affect the current 24-hour energy schedule,
   use no_op.

9) If a battery reserve is written as a percentage,
   calculate the kWh value using the supplied battery capacity.


Required structured_adjustment shapes:

solar_reduction:
{
  "hours": [...],
  "factor": number
}

minimum_battery_reserve:
{
  "hours": [...],
  "minimum_energy_kwh": number
}

no_charge_window:
{
  "hours": [...]
}

no_discharge_window:
{
  "hours": [...]
}

max_grid_window:
{
  "hours": [...],
  "max_grid_kwh": number
}

no_op:
null


Return ONLY valid JSON.

Required outer format:

{
  "directives": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": {
        "hours": [13, 14],
        "factor": 0.2
      },
      "explanation": "Short explanation."
    }
  ]
}
""".strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    """
    Extract JSON from the LLM response.
    Also removes Markdown ```json code fences if the model adds them.
    """

    text = text.strip()

    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    try:
        obj = json.loads(text)

    except json.JSONDecodeError:

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                "LLM did not return a valid JSON object"
            )

        obj = json.loads(
            text[start : end + 1]
        )

    if not isinstance(obj, dict):
        raise ValueError(
            "LLM output root must be a JSON object"
        )

    return obj


async def interpret_notes_with_llm(
    req: OptimizeRequest,
) -> list[dict[str, Any]]:

    """
    Send operator notes to an OpenAI-compatible LLM API.

    Required .env variables:

    LLM_API_URL
    LLM_API_KEY
    LLM_MODEL
    """

    api_url = os.getenv(
        "LLM_API_URL",
        "",
    ).strip()

    api_key = os.getenv(
        "LLM_API_KEY",
        "",
    ).strip()

    model = os.getenv(
        "LLM_MODEL",
        "",
    ).strip()


    # Check configuration
    if not api_url or not api_key or not model:
        raise RuntimeError(
            "LLM is not configured. "
            "Set LLM_API_URL, LLM_API_KEY, and LLM_MODEL."
        )


    # Only send information needed to interpret the note
    user_payload = {
        "scenario_id": req.scenario_id,
        "battery": req.battery.model_dump(),
        "operator_notes": req.operator_notes,
    }


    payload = {
        "model": model,

        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "Interpret the following GridWise operator notes.\n\n"
                    + json.dumps(
                        user_payload,
                        ensure_ascii=False,
                    )
                ),
            },
        ],

    }


    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


    # Controlled timeout.
    # Challenge total request limit is important, so do not make this huge.
    timeout = httpx.Timeout(
        connect=5.0,
        read=25.0,
        write=5.0,
        pool=5.0,
    )


    try:

        async with httpx.AsyncClient(
            timeout=timeout
        ) as client:

            response = await client.post(
                api_url,
                headers=headers,
                json=payload,
            )


    except httpx.ReadTimeout as exc:

        raise RuntimeError(
            "LLM provider timed out"
        ) from exc


    except httpx.ConnectTimeout as exc:

        raise RuntimeError(
            "Connection to LLM provider timed out"
        ) from exc


    except httpx.RequestError as exc:

        raise RuntimeError(
            "Could not connect to LLM provider"
        ) from exc


    # Provider error
    if response.status_code >= 400:

        raise RuntimeError(
            f"LLM provider returned HTTP "
            f"{response.status_code}"
        )


    try:

        data = response.json()

    except Exception as exc:

        raise RuntimeError(
            "LLM provider returned invalid JSON"
        ) from exc


    # OpenAI-compatible response format
    try:

        content = (
            data["choices"][0]
            ["message"]
            ["content"]
        )

    except Exception as exc:

        raise RuntimeError(
            "Unexpected LLM provider response shape"
        ) from exc


    if not isinstance(content, str):

        raise RuntimeError(
            "LLM response content is not text"
        )


    # Extract model JSON
    obj = _extract_json_object(content)


    directives = obj.get(
        "directives"
    )


    if not isinstance(directives, list):

        raise ValueError(
            "LLM JSON must contain a directives array"
        )


    return directives