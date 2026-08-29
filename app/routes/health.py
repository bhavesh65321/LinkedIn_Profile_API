from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.linkedin.client import LinkedInClient
from app.linkedin.exceptions import CredentialsMissingError, LinkedInError
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Service health")
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    if not settings.has_credentials:
        return HealthResponse(
            status="degraded",
            linkedin_credentials_configured=False,
            linkedin_session_ok=None,
            detail="Set LI_AT and JSESSIONID environment variables",
        )

    try:
        async with LinkedInClient(settings) as client:
            me = await client.ping_me()
        mini = None
        included = me.get("included") or []
        if included and isinstance(included[0], dict):
            mini = included[0]
        return HealthResponse(
            status="ok",
            linkedin_credentials_configured=True,
            linkedin_session_ok=True,
            detail="Voyager /me succeeded",
            extras={
                "public_identifier": (mini or {}).get("publicIdentifier"),
                "first_name": (mini or {}).get("firstName"),
            },
        )
    except CredentialsMissingError as exc:
        return HealthResponse(
            status="degraded",
            linkedin_credentials_configured=False,
            linkedin_session_ok=False,
            detail=exc.message,
        )
    except LinkedInError as exc:
        return HealthResponse(
            status="degraded",
            linkedin_credentials_configured=True,
            linkedin_session_ok=False,
            detail=exc.message,
        )
