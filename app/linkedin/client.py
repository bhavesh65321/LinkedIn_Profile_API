from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings
from app.linkedin.exceptions import (
    CredentialsMissingError,
    LinkedInAuthError,
    LinkedInError,
    LinkedInNotFoundError,
    LinkedInRateLimitError,
)

BASE_URL = "https://www.linkedin.com"

# Decorations tried in order — LinkedIn rotates versions; first success wins.
DASH_PROFILE_DECORATIONS = (
    "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93",
    "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-35",
    "com.linkedin.voyager.dash.deco.identity.profile.TopCardSupplementary-128",
    "com.linkedin.voyager.dash.deco.identity.profile.WebTopCardCore-16",
)

# GraphQL query family for profile cards (about / experience / education UI cards).
PROFILE_CARDS_QUERY_IDS = (
    "voyagerIdentityDashProfileCards.2d68c43b54ee24f8de25bc423c3cf7e4",
    "voyagerIdentityDashProfileCards.7916f566ebd5f1828abc6d47b425cac4",
)


class LinkedInClient:
    """Browserless Voyager client authenticated with session cookies."""

    def __init__(self, settings: Settings):
        if not settings.has_credentials:
            raise CredentialsMissingError()
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers=self._default_headers(),
            # Empty jar — auth cookies injected per request so LinkedIn
            # Set-Cookie "delete me" responses cannot wipe li_at mid-session.
            cookies=httpx.Cookies(),
        )

    def _auth_cookies(self) -> dict[str, str]:
        jsession = self._settings.csrf_token
        cookies = {
            "li_at": self._settings.li_at.strip(),
            "JSESSIONID": f'"{jsession}"' if not jsession.startswith('"') else jsession,
            "liap": "true",
        }
        if self._settings.li_a.strip():
            cookies["li_a"] = self._settings.li_a.strip()
        if self._settings.bcookie.strip():
            cookies["bcookie"] = self._settings.bcookie.strip().strip('"')
        if self._settings.bscookie.strip():
            cookies["bscookie"] = self._settings.bscookie.strip().strip('"')
        return cookies

    def _default_headers(self) -> dict[str, str]:
        csrf = self._settings.csrf_token.strip('"')
        return {
            "user-agent": self._settings.user_agent,
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "accept-language": "en-US,en;q=0.9",
            "csrf-token": csrf,
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": "en_US",
            "x-li-track": json.dumps(
                {
                    "clientVersion": "1.13.3520",
                    "mpVersion": "1.13.3520",
                    "osName": "web",
                    "timezoneOffset": 330,
                    "timezone": "Asia/Kolkata",
                    "deviceFormFactor": "DESKTOP",
                    "mpName": "voyager-web",
                }
            ),
            "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24", "Google Chrome";v="131"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "referer": f"{BASE_URL}/feed/",
            "origin": BASE_URL,
        }

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> LinkedInClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("http") else path
        try:
            response = await self._client.get(
                url,
                params=params,
                cookies=self._auth_cookies(),
            )
        except httpx.TimeoutException as exc:
            raise LinkedInError(
                "LinkedIn request timed out",
                code="linkedin_timeout",
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            raise LinkedInError(
                f"LinkedIn network error: {exc.__class__.__name__}",
                code="linkedin_network_error",
                status_code=502,
            ) from exc
        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        status = response.status_code
        if status in {401, 403}:
            raise LinkedInAuthError(
                f"LinkedIn rejected the session (HTTP {status}). Refresh LI_AT / JSESSIONID in .env."
            )
        if status == 429:
            raise LinkedInRateLimitError()
        if status == 404:
            raise LinkedInNotFoundError()
        if status >= 400:
            body_preview = response.text[:400]
            raise LinkedInError(
                f"LinkedIn API error HTTP {status}: {body_preview}",
                code="linkedin_http_error",
                status_code=502,
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise LinkedInError("LinkedIn returned a non-JSON body") from exc

    async def ping_me(self) -> dict[str, Any]:
        return await self._get("/voyager/api/me")

    async def fetch_profile_bundle(self, public_identifier: str) -> dict[str, Any]:
        """
        Hit multiple Voyager endpoints and return raw payloads for normalization.

        Strategy (all HTTP, no browser):
        1. Classic profileView — richest single call historically
        2. Dash FullProfile decorations — modern SPA payloads
        3. Section REST endpoints — skills / certs / languages / network
        4. Optional GraphQL profile cards — about / card layout sections
        """
        profile_view: dict[str, Any] | None = None
        profile_view_error: str | None = None
        profile_view_missing = False
        try:
            profile_view = await self._get(
                f"/voyager/api/identity/profiles/{quote(public_identifier, safe='')}/profileView"
            )
        except LinkedInNotFoundError:
            profile_view_missing = True
        except LinkedInError as exc:
            profile_view_error = str(exc.message)

        dash_profile: dict[str, Any] | None = None
        dash_saw_not_found = False
        for decoration in DASH_PROFILE_DECORATIONS:
            try:
                dash_profile = await self._get(
                    "/voyager/api/identity/dash/profiles",
                    params={
                        "q": "memberIdentity",
                        "memberIdentity": public_identifier,
                        "decorationId": decoration,
                    },
                )
                if dash_profile.get("elements") or dash_profile.get("included"):
                    break
            except LinkedInNotFoundError:
                dash_saw_not_found = True
                continue
            except LinkedInError:
                continue

        if profile_view is None and dash_profile is None:
            if profile_view_missing and dash_saw_not_found:
                raise LinkedInNotFoundError(
                    f"LinkedIn profile not found for '{public_identifier}'"
                )
            raise LinkedInError(
                profile_view_error or "Unable to resolve profile from Voyager endpoints"
            )

        profile_id = self._extract_profile_id(public_identifier, profile_view, dash_profile)

        skills = await self._safe_get(
            f"/voyager/api/identity/profiles/{quote(public_identifier, safe='')}/skills",
            params={"count": 100, "start": 0},
        )
        if skills is None and profile_id:
            skills = await self._safe_get(
                f"/voyager/api/identity/profiles/{quote(profile_id, safe='')}/skills",
                params={"count": 100, "start": 0},
            )

        certifications = await self._safe_get(
            f"/voyager/api/identity/profiles/{quote(public_identifier, safe='')}/certifications",
            params={"count": 100, "start": 0},
        )
        languages = await self._safe_get(
            f"/voyager/api/identity/profiles/{quote(public_identifier, safe='')}/languages",
            params={"count": 100, "start": 0},
        )
        network_info = await self._safe_get(
            f"/voyager/api/identity/profiles/{quote(public_identifier, safe='')}/networkinfo"
        )

        profile_cards: dict[str, Any] | None = None
        if profile_id:
            profile_cards = await self._fetch_profile_cards(profile_id)

        return {
            "public_identifier": public_identifier,
            "profile_id": profile_id,
            "profile_view": profile_view,
            "dash_profile": dash_profile,
            "skills": skills,
            "certifications": certifications,
            "languages": languages,
            "network_info": network_info,
            "profile_cards": profile_cards,
        }

    async def _safe_get(
        self, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        try:
            return await self._get(path, params=params)
        except LinkedInAuthError:
            raise
        except LinkedInRateLimitError:
            raise
        except LinkedInError:
            return None

    async def _fetch_profile_cards(self, profile_id: str) -> dict[str, Any] | None:
        encoded_urn = quote(f"urn:li:fsd_profile:{profile_id}", safe="")
        for query_id in PROFILE_CARDS_QUERY_IDS:
            path = (
                "/voyager/api/graphql"
                f"?includeWebMetadata=true"
                f"&variables=(profileUrn:{encoded_urn})"
                f"&queryId={query_id}"
            )
            try:
                data = await self._get(path)
                if data.get("included") or data.get("data"):
                    return data
            except LinkedInError:
                continue
        return None

    @staticmethod
    def _extract_profile_id(
        public_identifier: str,
        profile_view: dict[str, Any] | None,
        dash_profile: dict[str, Any] | None,
    ) -> str | None:
        if profile_view:
            for key in ("profile", "*profile"):
                node = profile_view.get(key)
                if isinstance(node, dict):
                    urn = node.get("entityUrn") or node.get("objectUrn")
                    if isinstance(urn, str) and ":" in urn:
                        return urn.rsplit(":", 1)[-1]
            included = profile_view.get("included") or []
            for item in included:
                if not isinstance(item, dict):
                    continue
                if item.get("publicIdentifier") == public_identifier:
                    urn = item.get("entityUrn") or item.get("objectUrn")
                    if isinstance(urn, str) and ":" in urn:
                        return urn.rsplit(":", 1)[-1]

        if dash_profile:
            for element in dash_profile.get("elements") or []:
                if not isinstance(element, dict):
                    continue
                urn = element.get("entityUrn")
                if isinstance(urn, str) and "fsd_profile" in urn:
                    return urn.rsplit(":", 1)[-1]
            for item in dash_profile.get("included") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("publicIdentifier") == public_identifier:
                    urn = item.get("entityUrn")
                    if isinstance(urn, str) and ":" in urn:
                        return urn.rsplit(":", 1)[-1]
                actions = item.get("profileStatefulProfileActions") or {}
                overflow = actions.get("overflowActions") or []
                for action in overflow:
                    if not isinstance(action, dict):
                        continue
                    report = action.get("report") or {}
                    author = report.get("authorProfileId")
                    if author:
                        return str(author)
        return None
