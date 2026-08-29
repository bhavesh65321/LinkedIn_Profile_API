"""Comprehensive regression tests for LinkedIn Profile API."""
from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.linkedin.client import LinkedInClient
from app.linkedin.exceptions import (
    CredentialsMissingError,
    InvalidProfileUrlError,
    LinkedInAuthError,
    LinkedInError,
    LinkedInNotFoundError,
)
from app.linkedin.normalize import normalize_profile
from app.linkedin.parser import extract_public_identifier
from app.main import app


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.linkedin.com/in/williamhgates/", "williamhgates"),
        ("https://linkedin.com/in/jane-doe-123", "jane-doe-123"),
        ("http://www.linkedin.com/in/foo_bar/", "foo_bar"),
        ("linkedin.com/in/no-scheme", "no-scheme"),
        ("https://www.linkedin.com/in/name%2Dwith%2Dencoding/", "name-with-encoding"),
        ("https://www.linkedin.com/in/slug/?trk=nav", "slug"),
        ("https://linkedin.cn/in/china-user/", "china-user"),
        ("  https://www.linkedin.com/in/padded/  ", "padded"),
    ],
)
def test_parser_accepts_valid_urls(url: str, expected: str) -> None:
    assert extract_public_identifier(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "https://google.com/in/foo",
        "https://www.linkedin.com/company/google/",
        "https://www.linkedin.com/school/mit/",
        "https://www.linkedin.com/in/",
        "https://www.linkedin.com/in/pub/",
        "https://www.linkedin.com/feed/",
        "not a url at all",
    ],
)
def test_parser_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(InvalidProfileUrlError):
        extract_public_identifier(url)


# ---------------------------------------------------------------------------
# Normalize — crashes & data bugs
# ---------------------------------------------------------------------------


def test_normalize_handles_string_view_refs_without_crashing() -> None:
    """LinkedIn often returns positionGroupView as a URN string, not an object."""
    bundle = {
        "public_identifier": "ada",
        "profile_view": {
            "profile": {
                "firstName": "Ada",
                "lastName": "Lovelace",
                "headline": "Analyst",
            },
            "positionGroupView": "urn:li:fs_positionGroupView:1",
            "educationView": "urn:li:fs_educationView:1",
            "skillView": "urn:li:fs_skillView:1",
        },
        "skills": None,
        "certifications": None,
        "languages": None,
        "network_info": None,
        "dash_profile": None,
        "profile_cards": None,
    }
    result = normalize_profile(bundle, "https://www.linkedin.com/in/ada/")
    assert result.first_name == "Ada"
    assert result.experience == []
    assert result.education == []


def test_normalize_resolves_urn_elements_from_included() -> None:
    bundle = {
        "public_identifier": "ada",
        "profile_view": {
            "profile": {"firstName": "Ada", "lastName": "Lovelace"},
            "positionGroupView": {
                "elements": ["urn:li:fs_positionGroup:1"],
            },
            "included": [
                {
                    "entityUrn": "urn:li:fs_positionGroup:1",
                    "$type": "com.linkedin.voyager.identity.profile.PositionGroup",
                    "company": {"name": "Analytical Engines", "universalName": "ae"},
                    "profilePositionInPositionGroup": {
                        "elements": [
                            {
                                "title": "Engineer",
                                "timePeriod": {
                                    "startDate": {"year": 2020, "month": 1},
                                },
                            }
                        ]
                    },
                }
            ],
        },
        "skills": None,
        "certifications": None,
        "languages": None,
        "network_info": None,
        "dash_profile": None,
        "profile_cards": None,
    }
    result = normalize_profile(bundle, "https://www.linkedin.com/in/ada/")
    assert len(result.experience) == 1
    assert result.experience[0].title == "Engineer"
    assert result.experience[0].company == "Analytical Engines"
    assert result.experience[0].is_current is True


def test_dash_merge_does_not_wipe_profile_view_fields() -> None:
    """If profileView has location/about but missing name pieces, dash Nones must not clobber."""
    bundle = {
        "public_identifier": "ada",
        "profile_view": {
            "profile": {
                # missing firstName triggers dash merge
                "lastName": "Lovelace",
                "summary": "Kept about",
                "geoLocationName": "London",
                "headline": "Kept headline",
            }
        },
        "dash_profile": {
            "elements": [
                {
                    "publicIdentifier": "ada",
                    "firstName": "Ada",
                    "lastName": "Lovelace",
                    "headline": None,
                    "geoLocation": None,
                }
            ]
        },
        "skills": None,
        "certifications": None,
        "languages": None,
        "network_info": None,
        "profile_cards": None,
    }
    result = normalize_profile(bundle, "https://www.linkedin.com/in/ada/")
    assert result.first_name == "Ada"
    assert result.about == "Kept about"
    assert result.location == "London"
    assert result.headline == "Kept headline"


def test_follower_count_zero_is_preserved() -> None:
    bundle = {
        "public_identifier": "ada",
        "profile_view": {"profile": {"firstName": "Ada", "lastName": "L"}},
        "network_info": {"followersCount": 0, "connectionsCount": 0},
        "skills": None,
        "certifications": None,
        "languages": None,
        "dash_profile": None,
        "profile_cards": None,
    }
    result = normalize_profile(bundle, "https://www.linkedin.com/in/ada/")
    assert result.follower_count == 0
    assert result.connection_count == 0


def test_picture_url_from_vector_artifacts() -> None:
    bundle = {
        "public_identifier": "ada",
        "profile_view": {
            "profile": {
                "firstName": "Ada",
                "lastName": "L",
                "profilePicture": {
                    "displayImageReference": {
                        "vectorImage": {
                            "rootUrl": "https://media.licdn.com/img/",
                            "artifacts": [
                                {"width": 100, "fileIdentifyingUrlPathSegment": "small.jpg"},
                                {"width": 800, "fileIdentifyingUrlPathSegment": "large.jpg"},
                            ],
                        }
                    }
                },
            }
        },
        "skills": None,
        "certifications": None,
        "languages": None,
        "network_info": None,
        "dash_profile": None,
        "profile_cards": None,
    }
    result = normalize_profile(bundle, "https://www.linkedin.com/in/ada/")
    assert result.profile_picture == "https://media.licdn.com/img/large.jpg"


def test_experience_from_cards_and_about() -> None:
    bundle = {
        "public_identifier": "ada",
        "profile_view": {"profile": {"firstName": "Ada", "lastName": "L"}},
        "skills": None,
        "certifications": None,
        "languages": None,
        "network_info": None,
        "dash_profile": None,
        "profile_cards": {
            "included": [
                {
                    "entityUrn": "urn:li:fsd_profileCard:ABOUT",
                    "topComponents": [
                        {},
                        {
                            "components": {
                                "textComponent": {"text": {"text": "Hello about"}}
                            }
                        },
                    ],
                },
                {
                    "entityUrn": "urn:li:fsd_profileCard:EXPERIENCE",
                    "topComponents": [
                        {},
                        {
                            "components": {
                                "fixedListComponent": {
                                    "components": [
                                        {
                                            "components": {
                                                "entityComponent": {
                                                    "title": {"text": "CEO"},
                                                    "subtitle": {"text": "Contoso"},
                                                    "caption": {"text": "Jan 2020 - Present · 4 yrs"},
                                                    "metadata": {"text": "Remote"},
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        },
                    ],
                },
            ]
        },
    }
    result = normalize_profile(bundle, "https://www.linkedin.com/in/ada/")
    assert result.about == "Hello about"
    assert result.experience[0].title == "CEO"
    assert result.experience[0].is_current is True
    assert result.experience[0].start_date is not None
    assert result.experience[0].start_date.year == 2020
    assert result.experience[0].start_date.month == 1


# ---------------------------------------------------------------------------
# Client behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_requires_credentials() -> None:
    with pytest.raises(CredentialsMissingError):
        LinkedInClient(Settings(li_at="", jsessionid=""))


@pytest.mark.asyncio
async def test_profile_view_404_falls_through_to_dash() -> None:
    settings = Settings(li_at="fake_li_at", jsessionid="ajax:123")
    client = LinkedInClient(settings)

    async def fake_get(path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if "profileView" in path:
            raise LinkedInNotFoundError()
        if "dash/profiles" in path:
            return {
                "elements": [
                    {
                        "entityUrn": "urn:li:fsd_profile:ABC123",
                        "publicIdentifier": "ada",
                        "firstName": "Ada",
                        "lastName": "Lovelace",
                    }
                ]
            }
        return {"elements": []}

    with patch.object(client, "_get", side_effect=fake_get):
        bundle = await client.fetch_profile_bundle("ada")

    await client.aclose()
    assert bundle["profile_view"] is None
    assert bundle["dash_profile"]["elements"][0]["firstName"] == "Ada"
    assert bundle["profile_id"] == "ABC123"


@pytest.mark.asyncio
async def test_all_endpoints_missing_raises_not_found_or_error() -> None:
    settings = Settings(li_at="fake_li_at", jsessionid="ajax:123")
    client = LinkedInClient(settings)

    async def always_404(path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise LinkedInNotFoundError()

    with patch.object(client, "_get", side_effect=always_404):
        with pytest.raises((LinkedInNotFoundError, LinkedInError)):
            await client.fetch_profile_bundle("missing-user")

    await client.aclose()


# ---------------------------------------------------------------------------
# API (TestClient)
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client() -> TestClient:
    get_settings.cache_clear()

    def override_settings() -> Settings:
        return Settings(li_at="test_li_at", jsessionid="ajax:999")

    app.dependency_overrides[get_settings] = override_settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_health_without_credentials() -> None:
    get_settings.cache_clear()

    def override() -> Settings:
        return Settings(li_at="", jsessionid="")

    app.dependency_overrides[get_settings] = override
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["linkedin_credentials_configured"] is False
        assert body["status"] == "degraded"
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_profile_invalid_url_returns_400(api_client: TestClient) -> None:
    res = api_client.post("/v1/profile", json={"url": "https://example.com/x"})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "invalid_url"


def test_profile_missing_url_body_returns_422(api_client: TestClient) -> None:
    res = api_client.post("/v1/profile", json={})
    assert res.status_code == 422


def test_profile_get_and_post_success(api_client: TestClient) -> None:
    fake_bundle = {
        "public_identifier": "williamhgates",
        "profile_id": "x",
        "profile_view": {
            "profile": {
                "firstName": "Bill",
                "lastName": "Gates",
                "headline": "Co-chair",
                "summary": "About",
                "geoLocationName": "USA",
            },
            "positionGroupView": {"elements": []},
            "educationView": {"elements": []},
        },
        "skills": {"elements": [{"name": "Leadership", "endorsementCount": 5}]},
        "certifications": {"elements": []},
        "languages": {"elements": []},
        "network_info": {"followersCount": 10, "connectionsCount": 500},
        "dash_profile": None,
        "profile_cards": None,
    }

    with patch(
        "app.routes.profile.LinkedInClient.fetch_profile_bundle",
        new_callable=AsyncMock,
        return_value=fake_bundle,
    ):
        post = api_client.post(
            "/v1/profile",
            json={"url": "https://www.linkedin.com/in/williamhgates/"},
        )
        get = api_client.get(
            "/v1/profile",
            params={"url": "https://www.linkedin.com/in/williamhgates/"},
        )

    assert post.status_code == 200, post.text
    assert get.status_code == 200, get.text
    assert post.json()["full_name"] == "Bill Gates"
    assert post.json()["skills"][0]["name"] == "Leadership"
    assert get.json()["public_identifier"] == "williamhgates"


def test_profile_maps_auth_error_to_502(api_client: TestClient) -> None:
    with patch(
        "app.routes.profile.LinkedInClient.fetch_profile_bundle",
        new_callable=AsyncMock,
        side_effect=LinkedInAuthError(),
    ):
        res = api_client.post(
            "/v1/profile",
            json={"url": "https://www.linkedin.com/in/someone/"},
        )
    assert res.status_code == 502
    assert res.json()["detail"]["code"] == "linkedin_auth_error"


def test_root_and_openapi(api_client: TestClient) -> None:
    assert api_client.get("/").status_code == 200
    assert api_client.get("/openapi.json").status_code == 200
    assert api_client.get("/docs").status_code == 200
