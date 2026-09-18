
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx


def comparable_directive(item: dict) -> dict:
    return {
        "note_index": item["note_index"],
        "applies": item["applies"],
        "directive_type": item["directive_type"],
        "structured_adjustment": item["structured_adjustment"],
    }


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/test_public_cases.py "
            "PATH_TO_PUBLIC_SAMPLE_CASES.json [BASE_URL]"
        )
        raise SystemExit(2)

    case_path = Path(sys.argv[1])
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"

    data = json.loads(case_path.read_text(encoding="utf-8"))
    cases = data["cases"]

    passed = 0

    for case in cases:
        r = httpx.post(
            f"{base_url}/optimize-energy",
            json=case["input"],
            timeout=35.0,
        )

        if r.status_code != 200:
            print(case["id"], "FAIL HTTP", r.status_code, r.text[:200])
            continue

        actual = r.json()
        expected = case["expected_output"]

        actual_d = [
            comparable_directive(x)
            for x in actual["directive_interpretation"]
        ]
        expected_d = [
            comparable_directive(x)
            for x in expected["directive_interpretation"]
        ]

        if actual_d != expected_d:
            print(case["id"], "FAIL directive interpretation")
            print(" expected:", expected_d)
            print(" actual  :", actual_d)
            continue

        # Reference schedules may differ while still being equivalently optimal,
        # so do not require hourly_plan byte-for-byte equality.
        print(case["id"], "PASS interpretation", "cost=", actual["total_cost_bdt"])
        passed += 1

    print(f"\nPassed directive interpretation: {passed}/{len(cases)}")


if __name__ == "__main__":
    main()
