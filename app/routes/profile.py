from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.linkedin.client import LinkedInClient
from app.linkedin.exceptions import LinkedInError
from app.linkedin.normalize import normalize_profile
from app.linkedin.parser import extract_public_identifier
from app.schemas import ErrorResponse, ProfileRequest, ProfileResponse

router = APIRouter(tags=["profile"])


def _error_payload(exc: LinkedInError) -> dict:
    return {"error": exc.message, "detail": None, "code": exc.code}


@router.post(
    "/v1/profile",
    response_model=ProfileResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Fetch a LinkedIn profile by URL (JSON body)",
)
async def fetch_profile_post(
    body: ProfileRequest,
    settings: Settings = Depends(get_settings),
) -> ProfileResponse:
    return await _fetch_profile(body.url, settings)


@router.get(
    "/v1/profile",
    response_model=ProfileResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Fetch a LinkedIn profile by URL (query param)",
)
async def fetch_profile_get(
    url: str = Query(
        ...,
        description="LinkedIn profile URL",
        examples=["https://www.linkedin.com/in/williamhgates/"],
    ),
    settings: Settings = Depends(get_settings),
) -> ProfileResponse:
    return await _fetch_profile(url, settings)


async def _fetch_profile(url: str, settings: Settings) -> ProfileResponse:
    try:
        public_identifier = extract_public_identifier(url)
        async with LinkedInClient(settings) as client:
            bundle = await client.fetch_profile_bundle(public_identifier)
        canonical = f"https://www.linkedin.com/in/{public_identifier}/"
        return normalize_profile(bundle, canonical)
    except LinkedInError as exc:
        raise HTTPException(status_code=exc.status_code, detail=_error_payload(exc)) from exc
