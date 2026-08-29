from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routes import health, profile

app = FastAPI(
    title="LinkedIn Profile API",
    description=(
        "Browserless reverse-engineered Voyager API wrapper. "
        "Pass a LinkedIn profile URL and receive structured JSON."
    ),
    version="1.0.0",
    contact={"name": "LinkedIn Profile API"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(profile.router)


@app.get("/", include_in_schema=False)
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "service": "LinkedIn Profile API",
            "docs": "/docs",
            "health": "/health",
            "endpoints": {
                "POST /v1/profile": {"url": "https://www.linkedin.com/in/{slug}/"},
                "GET /v1/profile": "?url=https://www.linkedin.com/in/{slug}/",
            },
        }
    )
