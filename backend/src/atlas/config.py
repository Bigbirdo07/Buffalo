"""Application configuration with no hidden global model state."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str = "development"
    monarch_api_base: str = "https://api.monarchinitiative.org/v3/api"
    database_url: str | None = None
    neo4j_uri: str | None = None

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            monarch_api_base=os.getenv(
                "MONARCH_API_BASE", "https://api.monarchinitiative.org/v3/api"
            ),
            database_url=os.getenv("DATABASE_URL"),
            neo4j_uri=os.getenv("NEO4J_URI"),
        )

