"""FastAPI application for the Orion Pipeline HTTP API."""

from fastapi import FastAPI

from api.routes import health, pdf, site

app = FastAPI(
    title="Orion Pipeline API",
    description="HTTP API for AWS corpus ingestion and site scraping.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(health.router, prefix="/api")
app.include_router(pdf.router, prefix="/api")
app.include_router(site.router, prefix="/api")
