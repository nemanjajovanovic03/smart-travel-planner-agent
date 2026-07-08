from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from .agent import run_travel_agent
from .config import Settings
from .data_loader import build_trip_request_from_args, load_trip_request
from .output_writer import to_markdown, write_json, write_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smart Travel Planner Agent - LangChain/OpenAI travel planning assistant."
    )
    parser.add_argument("--input", help="Path to JSON file with trip request.")
    parser.add_argument("--destination", help="Destination city or region.")
    parser.add_argument("--start-date", help="Trip start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Trip end date, YYYY-MM-DD.")
    parser.add_argument("--travelers", type=int, default=1)
    parser.add_argument("--budget", type=float, help="Total budget in EUR.")
    parser.add_argument("--interests", nargs="*", default=[], help="Interests, e.g. history museums food.")
    parser.add_argument("--origin", help="Origin city.")
    parser.add_argument("--accommodation-budget", type=float)
    parser.add_argument("--food-budget", type=float)
    parser.add_argument("--activities-budget", type=float)
    parser.add_argument("--pace", choices=["relaxed", "balanced", "intense"], default="balanced")
    parser.add_argument("--language", choices=["sr", "en"], default="sr")
    parser.add_argument("--env-file", help="Optional path to .env file.")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="both")
    parser.add_argument("--output", default="outputs/travel_plan", help="Output path without extension.")
    parser.add_argument("--mock", action="store_true", help="Offline demo mode without OpenAI calls.")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args()

    try:
        trip_request = load_trip_request(args.input) if args.input else build_trip_request_from_args(args)
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        parser.error(str(exc))
        return

    settings = Settings.from_env(args.env_file)
    try:
        plan = run_travel_agent(trip_request, settings, mock=args.mock)
    except RuntimeError as exc:
        parser.exit(1, f"Error: {exc}\n")

    output_base = Path(args.output)
    written = []
    if args.format in {"json", "both"}:
        written.append(write_json(plan, output_base.with_suffix(".json")))
    if args.format in {"markdown", "both"}:
        written.append(write_markdown(plan, output_base.with_suffix(".md")))

    print(to_markdown(plan))
    print("\nSaved files:")
    for path in written:
        print(f"- {path}")
    if args.mock:
        print("\nNote: --mock mode was used. Run without --mock and configure OPENAI_API_KEY for real LLM output.")
