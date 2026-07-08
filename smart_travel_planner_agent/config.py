from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Keeps --mock usable before dependency install.
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


@dataclass(frozen=True)
class Settings:
    openai_api_key: str | None
    openai_model: str
    weather_api_key: str | None
    weather_api_url: str
    output_dir: Path

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "Settings":
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            weather_api_key=os.getenv("WEATHER_API_KEY"),
            weather_api_url=os.getenv("WEATHER_API_URL", "https://api.openweathermap.org"),
            output_dir=Path(os.getenv("OUTPUT_DIR", "outputs")),
        )

    def require_openai(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Add it to .env or run with --mock for an offline demo."
            )
