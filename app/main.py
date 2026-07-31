"""FastAPI application factory.

Run the live server with:

    uv run uvicorn app.main:app --reload

then open http://127.0.0.1:8000/ (or /report for the live email template
rendered against the current Google Sheet data).
"""
from fastapi import FastAPI

from .api.routes import router
from .config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Export KPI Automation",
        version="0.1.0",
        description="Live preview + JSON of the SCM Export KPI report.",
    )
    app.include_router(router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)

