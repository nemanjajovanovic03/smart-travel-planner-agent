from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TripRequest(BaseModel):
    destination: str = Field(..., min_length=2, description="Destination city or region.")
    start_date: date = Field(..., description="Trip start date.")
    end_date: date = Field(..., description="Trip end date.")
    travelers: int = Field(1, ge=1, le=20, description="Number of travelers.")
    budget_eur: float | None = Field(None, gt=0, description="Total approximate budget in EUR.")
    interests: list[str] = Field(default_factory=list, description="Traveler interests.")
    origin: str | None = Field(None, description="Optional origin city.")
    accommodation_budget_eur: float | None = Field(None, ge=0)
    food_budget_eur: float | None = Field(None, ge=0)
    activities_budget_eur: float | None = Field(None, ge=0)
    pace: Literal["relaxed", "balanced", "intense"] = "balanced"
    language: Literal["sr", "en"] = "sr"

    @field_validator("destination", "origin")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("interests", mode="before")
    @classmethod
    def normalize_interests(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("interests must be a string or a list of strings")

    @model_validator(mode="after")
    def validate_dates(self) -> "TripRequest":
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


class WeatherSummary(BaseModel):
    source: str = "openweather"
    destination: str
    summary: str
    temperature_c: float | None = None
    feels_like_c: float | None = None
    humidity_percent: int | None = None
    wind_speed_mps: float | None = None
    raw_status: str = "ok"
    notes: list[str] = Field(default_factory=list)


class DailyPlanItem(BaseModel):
    time_of_day: str
    activity: str
    rationale: str
    estimated_cost_eur: float | None = None


class DailyPlan(BaseModel):
    day: int
    title: str
    weather_note: str | None = None
    activities: list[DailyPlanItem] = Field(default_factory=list)


class CostEstimate(BaseModel):
    transport_eur: float | None = None
    accommodation_eur: float | None = None
    food_eur: float | None = None
    activities_eur: float | None = None
    total_eur: float | None = None
    notes: list[str] = Field(default_factory=list)


class TravelPlan(BaseModel):
    destination: str
    period: str
    travelers: int
    summary: str
    transport_suggestion: str | None = None
    weather_notes: list[str] = Field(default_factory=list)
    daily_plan: list[DailyPlan] = Field(default_factory=list)
    estimated_costs: CostEstimate = Field(default_factory=CostEstimate)
    risks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
