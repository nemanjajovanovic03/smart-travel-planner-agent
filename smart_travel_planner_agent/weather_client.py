from __future__ import annotations

from datetime import date

from .models import WeatherSummary


class WeatherClientError(RuntimeError):
    pass


class OpenWeatherClient:
    def __init__(self, api_key: str | None, base_url: str = "https://api.openweathermap.org") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def get_weather(self, destination: str, start_date: date | None = None, end_date: date | None = None) -> WeatherSummary:
        if not self.api_key:
            return WeatherSummary(
                source="openweather-not-configured",
                destination=destination,
                summary="OpenWeather API key is not configured.",
                raw_status="missing_api_key",
                notes=[
                    "Set WEATHER_API_KEY in .env to use real weather data.",
                    "Agent can still generate a plan, but weather notes are not live.",
                ],
            )

        url = f"{self.base_url}/data/2.5/weather"
        try:
            import requests

            response = requests.get(
                url,
                params={"q": destination, "appid": self.api_key, "units": "metric"},
                timeout=10,
            )
            response.raise_for_status()
        except ImportError:
            return WeatherSummary(
                source="openweather-client-missing",
                destination=destination,
                summary="Weather client dependency is not installed.",
                raw_status="missing_requests",
                notes=["Run: pip install -r requirements.txt"],
            )
        except Exception as exc:
            return WeatherSummary(
                source="openweather-error",
                destination=destination,
                summary="Weather data is currently unavailable.",
                raw_status="api_error",
                notes=[f"OpenWeather request failed: {exc}"],
            )

        data = response.json()
        main = data.get("main", {})
        wind = data.get("wind", {})
        weather = data.get("weather") or [{}]
        description = weather[0].get("description", "weather data available")

        notes = []
        if start_date and end_date:
            notes.append(
                "OpenWeather current weather endpoint is used as a lightweight external data source; "
                "date-range forecast can be added later if the API plan supports it."
            )

        return WeatherSummary(
            destination=destination,
            summary=description,
            temperature_c=main.get("temp"),
            feels_like_c=main.get("feels_like"),
            humidity_percent=main.get("humidity"),
            wind_speed_mps=wind.get("speed"),
            notes=notes,
        )





