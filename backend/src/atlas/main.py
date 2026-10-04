"""FastAPI entry point."""

from __future__ import annotations

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="Rare Disease Evidence Refinement & Action Engine",
        version="0.1.0",
        description=(
            "Research evidence analysis only. This API does not diagnose disease "
            "or recommend treatment."
        ),
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
