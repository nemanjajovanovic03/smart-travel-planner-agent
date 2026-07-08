from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import TripRequest


def load_trip_request(path: str | Path) -> TripRequest:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {file_path}")

    try:
        payload: dict[str, Any] = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON input file: {file_path}") from exc

    return TripRequest.model_validate(payload)


def build_trip_request_from_args(args: Any) -> TripRequest:
    payload = {
        "destination": args.destination,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "travelers": args.travelers,
        "budget_eur": args.budget,
        "interests": args.interests,
        "origin": args.origin,
        "accommodation_budget_eur": args.accommodation_budget,
        "food_budget_eur": args.food_budget,
        "activities_budget_eur": args.activities_budget,
        "pace": args.pace,
        "language": args.language,
    }
    return TripRequest.model_validate({k: v for k, v in payload.items() if v is not None})
