from __future__ import annotations

import json

from .config import Settings
from .models import TripRequest
from .weather_client import OpenWeatherClient


def build_langchain_tools(settings: Settings, trip_request: TripRequest):
    try:
        from langchain_core.tools import tool
    except ImportError as exc:
        raise RuntimeError(
            "LangChain is not installed. Run: pip install -r requirements.txt"
        ) from exc

    weather_client = OpenWeatherClient(settings.weather_api_key, settings.weather_api_url)

    @tool
    def get_weather_forecast(destination: str) -> str:
        """Get live weather context for a destination using OpenWeather."""
        weather = weather_client.get_weather(
            destination=destination,
            start_date=trip_request.start_date,
            end_date=trip_request.end_date,
        )
        return weather.model_dump_json()

    @tool
    def estimate_trip_cost() -> str:
        """Estimate trip costs from user-provided budget categories."""
        total = trip_request.budget_eur
        accommodation = trip_request.accommodation_budget_eur
        food = trip_request.food_budget_eur
        activities = trip_request.activities_budget_eur
        known = sum(value or 0 for value in [accommodation, food, activities])
        remaining = (total - known) if total is not None else None
        payload = {
            "budget_eur": total,
            "accommodation_budget_eur": accommodation,
            "food_budget_eur": food,
            "activities_budget_eur": activities,
            "remaining_unallocated_eur": remaining,
            "notes": [
                "This is a rough planning estimate, not a booking quote.",
                "Transport booking data is outside the current agent scope.",
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    return [get_weather_forecast, estimate_trip_cost]
