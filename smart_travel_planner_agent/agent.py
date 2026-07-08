from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .config import Settings
from .models import CostEstimate, DailyPlan, DailyPlanItem, TravelPlan, TripRequest
from .prompts import HUMAN_PROMPT, SYSTEM_PROMPT
from .tools import build_langchain_tools
from .weather_client import OpenWeatherClient


def run_travel_agent(
    trip_request: TripRequest,
    settings: Settings,
    *,
    mock: bool = False,
) -> TravelPlan:
    if mock:
        return _complete_travel_plan(build_mock_plan(trip_request, settings), trip_request)

    settings.require_openai()

    try:
        return _run_modern_langchain_agent(trip_request, settings)
    except ImportError:
        try:
            return _run_legacy_langchain_agent(trip_request, settings)
        except ImportError as exc:
            raise RuntimeError(
                "LangChain dependencies are missing or incompatible. Run: pip install -r requirements.txt"
            ) from exc


def _build_user_prompt(trip_request: TripRequest) -> str:
    return HUMAN_PROMPT.format(
        trip_days=trip_request.days,
        trip_request_json=trip_request.model_dump_json(),
        output_schema=json.dumps(TravelPlan.model_json_schema(), ensure_ascii=False),
    )


def _run_modern_langchain_agent(trip_request: TripRequest, settings: Settings) -> TravelPlan:
    from langchain.agents import create_agent
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
        timeout=30,
        max_retries=0,
    )
    agent = create_agent(
        model=llm,
        tools=build_langchain_tools(settings, trip_request),
        system_prompt=SYSTEM_PROMPT,
        response_format=TravelPlan,
    )
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": _build_user_prompt(trip_request)}]}
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI/LangChain call failed: {exc}") from exc
    return _complete_travel_plan(_extract_travel_plan(result), trip_request)


def _run_legacy_langchain_agent(trip_request: TripRequest, settings: Settings) -> TravelPlan:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
        timeout=30,
        max_retries=0,
    )
    tools = build_langchain_tools(settings, trip_request)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=6)

    try:
        result = executor.invoke(
            {
                "trip_days": trip_request.days,
                "trip_request_json": trip_request.model_dump_json(),
                "output_schema": json.dumps(TravelPlan.model_json_schema(), ensure_ascii=False),
            }
        )
    except Exception as exc:
        raise RuntimeError(f"OpenAI/LangChain call failed: {exc}") from exc
    return _complete_travel_plan(_extract_travel_plan(result), trip_request)


def _extract_travel_plan(result: Any) -> TravelPlan:
    if isinstance(result, TravelPlan):
        return result

    if isinstance(result, dict):
        structured = result.get("structured_response")
        if structured is not None:
            return TravelPlan.model_validate(structured)

        output = result.get("output")
        if output:
            return parse_travel_plan(str(output))

        messages = result.get("messages") or []
        if messages:
            last_message = messages[-1]
            content = getattr(
                last_message,
                "content",
                last_message.get("content") if isinstance(last_message, dict) else "",
            )
            if isinstance(content, list):
                content = "\n".join(
                    str(part.get("text", part.get("content", part))) if isinstance(part, dict) else str(part)
                    for part in content
                )
            return parse_travel_plan(str(content))

    return parse_travel_plan(str(result))


def _complete_travel_plan(plan: TravelPlan, trip_request: TripRequest) -> TravelPlan:
    plan.destination = trip_request.destination
    plan.period = f"{trip_request.start_date.isoformat()} to {trip_request.end_date.isoformat()}"
    plan.travelers = trip_request.travelers

    if not plan.summary:
        plan.summary = _text(
            trip_request,
            sr=f"Plan putovanja za {trip_request.destination} sa fokusom na {', '.join(trip_request.interests) or 'lokalnu kulturu'}.",
            en=f"Travel plan for {trip_request.destination} focused on {', '.join(trip_request.interests) or 'local culture'}.",
        )

    if not plan.transport_suggestion:
        plan.transport_suggestion = _text(
            trip_request,
            sr="Prevoz nije povezan sa live servisom; proveriti lokalni prevoz i transfere pre polaska.",
            en="Transport booking data is outside the current agent scope; verify local transport before departure.",
        )

    plan.daily_plan = _complete_daily_plan(plan, trip_request)
    plan.estimated_costs = _complete_costs(plan, trip_request)
    plan.risks = _ensure_minimum_items(plan.risks, _default_risks(trip_request), minimum=3)
    plan.recommendations = _ensure_minimum_items(
        plan.recommendations,
        _default_recommendations(trip_request),
        minimum=3,
    )
    plan.data_sources = _ensure_data_sources(plan.data_sources, plan.weather_notes)
    if not plan.weather_notes:
        plan.weather_notes = [
            _text(
                trip_request,
                sr="Vremenske podatke proveriti pre polaska; agent koristi OpenWeather kada je API dostupan.",
                en="Check weather before departure; the agent uses OpenWeather when the API is available.",
            )
        ]
    return plan


def _complete_daily_plan(plan: TravelPlan, trip_request: TripRequest) -> list[DailyPlan]:
    expected_days = max(trip_request.days, 1)
    normalized: list[DailyPlan] = []
    existing_days = list(plan.daily_plan[:expected_days])

    for index in range(expected_days):
        day_number = index + 1
        if index < len(existing_days):
            day = existing_days[index]
            day.day = day_number
            if not day.title:
                day.title = _default_day_title(trip_request, day_number)
            day.activities = _complete_activities(day.activities, trip_request)
        else:
            day = _default_day_plan(trip_request, day_number)
        normalized.append(day)

    return normalized


def _complete_activities(activities: list[DailyPlanItem], trip_request: TripRequest) -> list[DailyPlanItem]:
    completed = list(activities)
    existing_slots = {item.time_of_day.strip().lower() for item in completed if item.time_of_day}

    for item in _default_day_activities(trip_request):
        if len(completed) >= 3:
            break
        if item.time_of_day.lower() not in existing_slots:
            completed.append(item)
            existing_slots.add(item.time_of_day.lower())

    while len(completed) < 3:
        completed.append(
            DailyPlanItem(
                time_of_day=f"slot-{len(completed) + 1}",
                activity=_text(
                    trip_request,
                    sr="Slobodno vreme za odmor ili dodatnu aktivnost prema interesovanjima.",
                    en="Free time for rest or an additional activity based on interests.",
                ),
                rationale=_text(
                    trip_request,
                    sr="Plan ostavlja fleksibilan prostor za promenu ritma.",
                    en="The plan keeps flexible space for changing the pace.",
                ),
                estimated_cost_eur=0,
            )
        )
    return completed


def _complete_costs(plan: TravelPlan, trip_request: TripRequest) -> CostEstimate:
    costs = plan.estimated_costs or CostEstimate()
    accommodation = _coalesce(costs.accommodation_eur, trip_request.accommodation_budget_eur)
    food = _coalesce(costs.food_eur, trip_request.food_budget_eur)
    activities = _coalesce(costs.activities_eur, trip_request.activities_budget_eur, _sum_activity_costs(plan))
    total = _coalesce(costs.total_eur, trip_request.budget_eur)
    transport = costs.transport_eur

    known_without_transport = sum(value or 0 for value in [accommodation, food, activities])
    if transport is None and total is not None:
        transport = max(total - known_without_transport, 0)

    if total is None:
        known_total = sum(value or 0 for value in [transport, accommodation, food, activities])
        total = known_total if known_total > 0 else None

    notes = list(costs.notes)
    if not notes:
        notes.append(
            _text(
                trip_request,
                sr="Procena troskova je okvirna i zasnovana na korisnickom budzetu i planiranim aktivnostima.",
                en="Cost estimate is approximate and based on the user budget and planned activities.",
            )
        )

    return CostEstimate(
        transport_eur=transport,
        accommodation_eur=accommodation,
        food_eur=food,
        activities_eur=activities,
        total_eur=total,
        notes=notes,
    )


def _sum_activity_costs(plan: TravelPlan) -> float | None:
    total = sum(
        item.estimated_cost_eur or 0
        for day in plan.daily_plan
        for item in day.activities
    )
    return total if total > 0 else None


def _default_day_plan(trip_request: TripRequest, day_number: int) -> DailyPlan:
    return DailyPlan(
        day=day_number,
        title=_default_day_title(trip_request, day_number),
        weather_note=_text(
            trip_request,
            sr="Plan prilagoditi aktuelnoj vremenskoj prognozi.",
            en="Adjust the plan to the current weather forecast.",
        ),
        activities=_default_day_activities(trip_request),
    )


def _default_day_title(trip_request: TripRequest, day_number: int) -> str:
    interests = ", ".join(trip_request.interests) if trip_request.interests else "lokalna kultura"
    return _text(
        trip_request,
        sr=f"Dan {day_number}: {trip_request.destination} kroz temu {interests}",
        en=f"Day {day_number}: {trip_request.destination} through {interests}",
    )


def _default_day_activities(trip_request: TripRequest) -> list[DailyPlanItem]:
    return [
        DailyPlanItem(
            time_of_day=_text(trip_request, sr="morning", en="morning"),
            activity=_text(
                trip_request,
                sr="Obilazak glavne znamenitosti i orijentacija u gradu.",
                en="Visit a major landmark and get oriented in the city.",
            ),
            rationale=_text(
                trip_request,
                sr="Prvi deo dana je dobar za aktivnosti koje traze vise energije.",
                en="The first part of the day works well for higher-energy activities.",
            ),
            estimated_cost_eur=20,
        ),
        DailyPlanItem(
            time_of_day=_text(trip_request, sr="afternoon", en="afternoon"),
            activity=_text(
                trip_request,
                sr="Muzej, lokalna cetvrt ili aktivnost povezana sa interesovanjima.",
                en="Museum, local neighborhood, or activity connected to interests.",
            ),
            rationale=_text(
                trip_request,
                sr="Plan koristi korisnikova interesovanja i ostavlja prostor za pauze.",
                en="The plan uses traveler interests and leaves room for breaks.",
            ),
            estimated_cost_eur=25,
        ),
        DailyPlanItem(
            time_of_day=_text(trip_request, sr="evening", en="evening"),
            activity=_text(
                trip_request,
                sr="Vecera u lokalnom restoranu i lagana setnja.",
                en="Dinner at a local restaurant and a relaxed walk.",
            ),
            rationale=_text(
                trip_request,
                sr="Vece je rezervisano za opusteniji ritam i lokalnu hranu.",
                en="Evening is reserved for a relaxed pace and local food.",
            ),
            estimated_cost_eur=30,
        ),
    ]


def _default_risks(trip_request: TripRequest) -> list[str]:
    return [
        _text(trip_request, sr="Popularne lokacije mogu imati guzve.", en="Popular locations can be crowded."),
        _text(trip_request, sr="Ulaznice za muzeje i atrakcije treba rezervisati unapred.", en="Museum and attraction tickets should be booked in advance."),
        _text(trip_request, sr="Plan treba prilagoditi vremenskim uslovima i radnom vremenu lokacija.", en="The plan should be adjusted to weather and venue opening hours."),
    ]


def _default_recommendations(trip_request: TripRequest) -> list[str]:
    return [
        _text(trip_request, sr="Ostaviti fleksibilan blok svakog dana za odmor ili promenu plana.", en="Keep a flexible block each day for rest or plan changes."),
        _text(trip_request, sr="Proveriti radno vreme atrakcija pre polaska.", en="Check attraction opening hours before departure."),
        _text(trip_request, sr="Sacuvati potvrde rezervacija i mapu lokacija za offline pristup.", en="Save booking confirmations and an offline map of locations."),
    ]


def _ensure_minimum_items(items: list[str], defaults: list[str], *, minimum: int) -> list[str]:
    result = [item for item in items if item]
    for item in defaults:
        if len(result) >= minimum:
            break
        if item not in result:
            result.append(item)
    return result


def _ensure_data_sources(items: list[str], weather_notes: list[str]) -> list[str]:
    result = [item for item in items if item]
    if "mock-planner" not in result:
        for source in ["openai", "langchain"]:
            if source not in result:
                result.append(source)

    weather_source = "openweather" if weather_notes else "openweather-fallback"
    has_weather_source = any(source.startswith("openweather") for source in result)
    if not has_weather_source:
        result.append(weather_source)
    return result


def _coalesce(*values: float | None) -> float | None:
    for value in values:
        if value is not None:
            return value
    return None


def _text(trip_request: TripRequest, *, sr: str, en: str) -> str:
    return sr if trip_request.language == "sr" else en


def parse_travel_plan(raw_output: str) -> TravelPlan:
    try:
        return TravelPlan.model_validate_json(raw_output)
    except ValidationError:
        pass

    match = re.search(r"\{.*\}", raw_output, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Agent did not return JSON. Raw output: {raw_output}")

    try:
        return TravelPlan.model_validate_json(match.group(0))
    except ValidationError as exc:
        raise ValueError(f"Agent JSON did not match TravelPlan schema: {exc}") from exc


def build_mock_plan(trip_request: TripRequest, settings: Settings) -> TravelPlan:
    weather = OpenWeatherClient(settings.weather_api_key, settings.weather_api_url).get_weather(
        trip_request.destination,
        trip_request.start_date,
        trip_request.end_date,
    )
    interests = ", ".join(trip_request.interests) if trip_request.interests else "lokalna kultura"
    days = min(trip_request.days, 5)
    daily_plan = []
    for day in range(1, days + 1):
        daily_plan.append(
            DailyPlan(
                day=day,
                title=f"Dan {day}: {trip_request.destination} kroz temu {interests}",
                weather_note=weather.summary,
                activities=[
                    DailyPlanItem(
                        time_of_day="morning",
                        activity="Obilazak glavne znamenitosti i orijentacija u gradu.",
                        rationale="Prvi deo dana je najbolji za aktivnosti koje traze vise energije.",
                        estimated_cost_eur=20,
                    ),
                    DailyPlanItem(
                        time_of_day="afternoon",
                        activity="Muzej, lokalna cetvrt ili aktivnost povezana sa interesovanjima.",
                        rationale="Plan koristi korisnikova interesovanja i ostavlja prostor za pauze.",
                        estimated_cost_eur=25,
                    ),
                    DailyPlanItem(
                        time_of_day="evening",
                        activity="Vecera u lokalnom restoranu i lagana setnja.",
                        rationale="Vece je rezervisano za opusteniji ritam i lokalnu hranu.",
                        estimated_cost_eur=30,
                    ),
                ],
            )
        )

    total = trip_request.budget_eur
    costs = CostEstimate(
        accommodation_eur=trip_request.accommodation_budget_eur,
        food_eur=trip_request.food_budget_eur,
        activities_eur=trip_request.activities_budget_eur or (days * 45),
        total_eur=total,
        notes=[
            "Mock rezim ne koristi OpenAI model i sluzi za lokalnu proveru strukture.",
            "Za stvarnu AI preporuku pokrenuti bez --mock i podesiti OPENAI_API_KEY.",
        ],
    )

    return TravelPlan(
        destination=trip_request.destination,
        period=f"{trip_request.start_date.isoformat()} to {trip_request.end_date.isoformat()}",
        travelers=trip_request.travelers,
        summary=(
            f"Predlog plana za {trip_request.destination} za {trip_request.travelers} putnika, "
            f"sa fokusom na: {interests}."
        ),
        transport_suggestion=(
            "Transport booking data is outside the current agent scope. "
            "Use this plan together with separately verified local transport options."
        ),
        weather_notes=[weather.summary, *weather.notes],
        daily_plan=daily_plan,
        estimated_costs=costs,
        risks=[
            "Popularne lokacije mogu imati guzve.",
            "Rezervisati ulaznice unapred za muzeje i atrakcije.",
            "Plan prilagoditi vremenskim uslovima.",
        ],
        recommendations=[
            "Ostaviti fleksibilan blok svakog dana za odmor ili promenu plana.",
            "Cuvati potvrde rezervacija i proveriti radno vreme atrakcija.",
        ],
        data_sources=[weather.source, "mock-planner"],
    )

