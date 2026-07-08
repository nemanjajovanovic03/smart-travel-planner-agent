from __future__ import annotations

import json
from pathlib import Path

from .models import TravelPlan


def write_json(plan: TravelPlan, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def write_markdown(plan: TravelPlan, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(to_markdown(plan), encoding="utf-8")
    return output_path


def to_markdown(plan: TravelPlan) -> str:
    lines = [
        f"# Smart Travel Plan: {plan.destination}",
        "",
        f"**Period:** {plan.period}",
        f"**Broj putnika:** {plan.travelers}",
        "",
        "## Sažetak",
        plan.summary,
        "",
    ]
    if plan.transport_suggestion:
        lines += ["## Prevoz", plan.transport_suggestion, ""]

    if plan.weather_notes:
        lines += ["## Vremenske napomene"]
        lines += [f"- {note}" for note in plan.weather_notes if note]
        lines.append("")

    lines.append("## Dnevni plan")
    for day in plan.daily_plan:
        lines += [f"### {day.title}"]
        if day.weather_note:
            lines.append(f"_Vreme:_ {day.weather_note}")
        for item in day.activities:
            cost = f" (~{item.estimated_cost_eur:.0f} EUR)" if item.estimated_cost_eur is not None else ""
            lines.append(f"- **{item.time_of_day}:** {item.activity}{cost}. {item.rationale}")
        lines.append("")

    lines += ["## Procena troškova"]
    costs = plan.estimated_costs
    has_cost_details = False
    for label, value in [
        ("Transport", costs.transport_eur),
        ("Smeštaj", costs.accommodation_eur),
        ("Hrana", costs.food_eur),
        ("Aktivnosti", costs.activities_eur),
        ("Ukupno", costs.total_eur),
    ]:
        if value is not None:
            lines.append(f"- {label}: {value:.2f} EUR")
            has_cost_details = True
    for note in costs.notes:
        lines.append(f"- {note}")
        has_cost_details = True
    if not has_cost_details:
        lines.append("- Procena troškova nije dostupna za ovaj zahtev.")
    lines.append("")

    if plan.risks:
        lines += ["## Rizici", *[f"- {risk}" for risk in plan.risks], ""]
    if plan.recommendations:
        lines += ["## Preporuke", *[f"- {rec}" for rec in plan.recommendations], ""]
    if plan.data_sources:
        lines += ["## Izvori podataka", *[f"- {source}" for source in plan.data_sources], ""]

    return "\n".join(lines).strip() + "\n"
