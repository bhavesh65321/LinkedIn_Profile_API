from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas import (
    CertificationItem,
    DateInfo,
    EducationItem,
    ExperienceItem,
    LanguageItem,
    ProfileResponse,
    SkillItem,
)


def normalize_profile(bundle: dict[str, Any], source_url: str) -> ProfileResponse:
    public_identifier = bundle["public_identifier"]
    profile_view = bundle.get("profile_view") or {}
    dash = bundle.get("dash_profile") or {}
    cards = bundle.get("profile_cards") or {}

    core = _merge_core(
        _core_from_profile_view(profile_view, public_identifier),
        _core_from_dash(dash, public_identifier),
    )

    about = core.get("about") or _about_from_cards(cards)
    experience = _experience_from_profile_view(profile_view) or _experience_from_cards(cards)
    education = _education_from_profile_view(profile_view) or _education_from_cards(cards)
    skills = _skills_from_payload(bundle.get("skills")) or _skills_from_profile_view(profile_view)
    certifications = _certs_from_payload(bundle.get("certifications")) or _certs_from_profile_view(
        profile_view
    )
    languages = _languages_from_payload(bundle.get("languages")) or _languages_from_profile_view(
        profile_view
    )

    network = bundle.get("network_info") or {}
    follower_count = _first_int(_dig(network, "followersCount"), core.get("follower_count"))
    connection_count = _first_int(_dig(network, "connectionsCount"), core.get("connection_count"))

    first = core.get("first_name")
    last = core.get("last_name")
    full_name = " ".join(p for p in [first, last] if p) or None

    return ProfileResponse(
        url=source_url if source_url.startswith("http") else f"https://www.linkedin.com/in/{public_identifier}/",
        public_identifier=public_identifier,
        profile_urn=core.get("profile_urn"),
        first_name=first,
        last_name=last,
        full_name=full_name,
        headline=core.get("headline"),
        location=core.get("location"),
        country=core.get("country"),
        industry=core.get("industry"),
        about=about,
        profile_picture=core.get("profile_picture"),
        background_image=core.get("background_image"),
        follower_count=_as_int(follower_count),
        connection_count=_as_int(connection_count),
        experience=experience,
        education=education,
        skills=skills,
        certifications=certifications,
        languages=languages,
        scraped_at=datetime.now(timezone.utc),
    )


def _core_from_profile_view(data: dict[str, Any], public_identifier: str) -> dict[str, Any]:
    profile = data.get("profile") or data.get("*profile") or {}
    if isinstance(profile, str):
        profile = _find_included(data, profile) or {}

    if not profile:
        for item in data.get("included") or []:
            if isinstance(item, dict) and item.get("publicIdentifier") == public_identifier:
                profile = item
                break

    geo = profile.get("geoLocationName") or profile.get("locationName")
    location = geo
    if not location and isinstance(profile.get("location"), dict):
        location = profile["location"].get("basicLocation", {}).get("countryCode")

    return {
        "first_name": profile.get("firstName"),
        "last_name": profile.get("lastName"),
        "headline": profile.get("headline"),
        "about": profile.get("summary"),
        "location": location,
        "country": _dig(profile, "location", "countryCode")
        or _dig(profile, "geoCountryName"),
        "industry": profile.get("industryName") or profile.get("industry"),
        "profile_urn": profile.get("entityUrn") or profile.get("objectUrn"),
        "profile_picture": _picture_url(profile.get("profilePicture") or profile.get("picture")),
        "background_image": _picture_url(
            profile.get("backgroundPicture") or profile.get("backgroundImage")
        ),
        "follower_count": profile.get("followerCount"),
        "connection_count": None,
    }


def _core_from_dash(data: dict[str, Any], public_identifier: str) -> dict[str, Any]:
    profile: dict[str, Any] = {}
    for element in data.get("elements") or []:
        if isinstance(element, dict) and (
            element.get("publicIdentifier") == public_identifier or element.get("firstName")
        ):
            profile = element
            break
    if not profile:
        for item in data.get("included") or []:
            if isinstance(item, dict) and item.get("publicIdentifier") == public_identifier:
                profile = item
                break

    location = None
    geo_location = profile.get("geoLocation")
    if isinstance(geo_location, dict):
        location = _dig(geo_location, "geo", "defaultLocalizedName")
    if not location:
        location = profile.get("locationName")

    return {
        "first_name": profile.get("firstName"),
        "last_name": profile.get("lastName"),
        "headline": profile.get("headline"),
        "about": None,
        "location": location,
        "country": None,
        "industry": None,
        "profile_urn": profile.get("entityUrn"),
        "profile_picture": _picture_url(profile.get("profilePicture")),
        "background_image": _picture_url(profile.get("backgroundPicture")),
        "follower_count": None,
        "connection_count": None,
    }


def _merge_core(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    """Prefer non-empty primary values; fill gaps from secondary without clobbering."""
    merged = dict(primary)
    for key, value in secondary.items():
        if _is_empty(merged.get(key)) and not _is_empty(value):
            merged[key] = value
    return merged


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == {} or value == []


def _view_elements(data: dict[str, Any], *view_keys: str) -> list[dict[str, Any]]:
    """
    Resolve LinkedIn view sections safely.

    LinkedIn may return:
    - {"elements": [ {...}, ... ]}
    - {"elements": ["urn:li:...", ...]} with objects in `included`
    - a bare URN string for the whole view
    """
    for key in view_keys:
        view = data.get(key)
        if view is None:
            continue
        if isinstance(view, str):
            resolved = _find_included(data, view)
            if isinstance(resolved, dict):
                view = resolved
            else:
                continue
        if not isinstance(view, dict):
            continue
        raw_elements = view.get("elements")
        if not isinstance(raw_elements, list):
            continue
        resolved_elements: list[dict[str, Any]] = []
        for element in raw_elements:
            if isinstance(element, dict):
                resolved_elements.append(element)
            elif isinstance(element, str):
                found = _find_included(data, element)
                if isinstance(found, dict):
                    resolved_elements.append(found)
        if resolved_elements:
            return resolved_elements
    return []


def _experience_from_profile_view(data: dict[str, Any]) -> list[ExperienceItem]:
    items: list[ExperienceItem] = []
    position_groups = _view_elements(data, "positionGroupView", "positionView")
    if not position_groups:
        position_groups = _elements_by_type(data, "positionGroup")

    for group in position_groups:
        company_name = (
            _dig(group, "company", "name")
            or _dig(group, "miniCompany", "name")
            or group.get("name")
        )
        company_url = None
        universal = _dig(group, "company", "universalName") or _dig(
            group, "miniCompany", "universalName"
        )
        if universal:
            company_url = f"https://www.linkedin.com/company/{universal}/"
        company_id = _dig(group, "company", "entityUrn") or _dig(group, "miniCompany", "entityUrn")
        if isinstance(company_id, str) and ":" in company_id:
            company_id = company_id.rsplit(":", 1)[-1]
        else:
            company_id = None

        positions = group.get("profilePositionInPositionGroup") or group.get("positions") or [group]
        if isinstance(positions, dict):
            positions = positions.get("elements") or []
        if isinstance(positions, list):
            resolved_positions: list[Any] = []
            for pos in positions:
                if isinstance(pos, dict):
                    resolved_positions.append(pos)
                elif isinstance(pos, str):
                    found = _find_included(data, pos)
                    if isinstance(found, dict):
                        resolved_positions.append(found)
            positions = resolved_positions

        for pos in positions:
            if not isinstance(pos, dict):
                continue
            title = pos.get("title") or pos.get("name")
            if not title and not company_name:
                continue
            time_period = pos.get("timePeriod") or {}
            start = _date_info(time_period.get("startDate"))
            end = _date_info(time_period.get("endDate"))
            items.append(
                ExperienceItem(
                    title=title,
                    company=pos.get("companyName") or company_name,
                    company_url=company_url,
                    company_linkedin_id=company_id,
                    location=pos.get("locationName") or pos.get("geoLocationName"),
                    description=pos.get("description"),
                    employment_type=pos.get("employmentType") or pos.get("employmentTypeUrn"),
                    start_date=start,
                    end_date=end,
                    is_current=end is None and start is not None,
                )
            )
    return items


def _education_from_profile_view(data: dict[str, Any]) -> list[EducationItem]:
    elements = _view_elements(data, "educationView") or _elements_by_type(data, "education")
    items: list[EducationItem] = []
    for edu in elements:
        school = (
            _dig(edu, "school", "name")
            or _dig(edu, "miniSchool", "name")
            or edu.get("schoolName")
        )
        school_url = None
        universal = _dig(edu, "school", "universalName") or _dig(edu, "miniSchool", "url")
        if isinstance(universal, str) and universal.startswith("http"):
            school_url = universal
        time_period = edu.get("timePeriod") or {}
        items.append(
            EducationItem(
                school=school,
                school_url=school_url,
                degree=edu.get("degreeName") or edu.get("degree"),
                field_of_study=edu.get("fieldOfStudy"),
                description=edu.get("description") or edu.get("activities"),
                start_date=_date_info(time_period.get("startDate")),
                end_date=_date_info(time_period.get("endDate")),
            )
        )
    return items


def _skills_from_profile_view(data: dict[str, Any]) -> list[SkillItem]:
    elements = _view_elements(data, "skillView") or _elements_by_type(data, "skill")
    return _map_skills(elements)


def _skills_from_payload(data: dict[str, Any] | None) -> list[SkillItem]:
    if not data:
        return []
    elements = data.get("elements") or []
    return _map_skills(elements)


def _map_skills(elements: list[Any]) -> list[SkillItem]:
    items: list[SkillItem] = []
    seen: set[str] = set()
    for skill in elements:
        if not isinstance(skill, dict):
            continue
        name = (
            skill.get("name")
            or _dig(skill, "skill", "name")
            or _dig(skill, "standardizedSkill", "name")
        )
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        endorsements = skill.get("endorsementCount") or skill.get("endorsements")
        items.append(SkillItem(name=name, endorsements=_as_int(endorsements)))
    return items


def _certs_from_profile_view(data: dict[str, Any]) -> list[CertificationItem]:
    elements = _view_elements(data, "certificationView") or _elements_by_type(data, "certification")
    return _map_certs(elements)


def _certs_from_payload(data: dict[str, Any] | None) -> list[CertificationItem]:
    if not data:
        return []
    return _map_certs(data.get("elements") or [])


def _map_certs(elements: list[Any]) -> list[CertificationItem]:
    items: list[CertificationItem] = []
    for cert in elements:
        if not isinstance(cert, dict):
            continue
        items.append(
            CertificationItem(
                name=cert.get("name") or cert.get("authority"),
                authority=cert.get("authority"),
                license_number=cert.get("licenseNumber"),
                url=cert.get("url"),
                issued_at=_date_info(cert.get("timePeriod", {}).get("startDate") or cert.get("start")),
                expires_at=_date_info(cert.get("timePeriod", {}).get("endDate") or cert.get("end")),
            )
        )
    return items


def _languages_from_profile_view(data: dict[str, Any]) -> list[LanguageItem]:
    elements = _view_elements(data, "languageView") or _elements_by_type(data, "language")
    return _map_languages(elements)


def _languages_from_payload(data: dict[str, Any] | None) -> list[LanguageItem]:
    if not data:
        return []
    return _map_languages(data.get("elements") or [])


def _map_languages(elements: list[Any]) -> list[LanguageItem]:
    items: list[LanguageItem] = []
    for lang in elements:
        if not isinstance(lang, dict):
            continue
        name = lang.get("name")
        if not name:
            continue
        proficiency = lang.get("proficiency")
        if isinstance(proficiency, str):
            proficiency = proficiency.replace("_", " ").title()
        items.append(LanguageItem(name=name, proficiency=proficiency))
    return items


def _about_from_cards(cards: dict[str, Any]) -> str | None:
    for item in cards.get("included") or []:
        if not isinstance(item, dict):
            continue
        urn = str(item.get("entityUrn") or "")
        if "ABOUT" not in urn.upper():
            continue
        text = _extract_card_text(item)
        if text:
            return text
    return None


def _experience_from_cards(cards: dict[str, Any]) -> list[ExperienceItem]:
    items: list[ExperienceItem] = []
    for entity in _card_entities(cards, "EXPERIENCE", exclude="VOLUNTEERING"):
        title = _dig(entity, "title", "text")
        company = _dig(entity, "subtitle", "text")
        dates = _dig(entity, "caption", "text")
        location = _dig(entity, "metadata", "text")
        description = _nested_description(entity)
        start, end, is_current = _parse_date_range_text(dates)
        items.append(
            ExperienceItem(
                title=title,
                company=company,
                company_url=_dig(entity, "image", "actionTarget"),
                location=location,
                description=description,
                start_date=start,
                end_date=end,
                is_current=is_current,
            )
        )
    return items


def _education_from_cards(cards: dict[str, Any]) -> list[EducationItem]:
    items: list[EducationItem] = []
    for entity in _card_entities(cards, "EDUCATION"):
        school = _dig(entity, "title", "text")
        degree_line = _dig(entity, "subtitle", "text")
        degree, field = _split_degree_field(degree_line)
        dates = _dig(entity, "caption", "text")
        start, end, _ = _parse_date_range_text(dates)
        items.append(
            EducationItem(
                school=school,
                school_url=_dig(entity, "image", "actionTarget"),
                degree=degree,
                field_of_study=field,
                description=_nested_description(entity),
                start_date=start,
                end_date=end,
            )
        )
    return items


def _card_entities(
    cards: dict[str, Any], section_token: str, exclude: str | None = None
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    for item in cards.get("included") or []:
        if not isinstance(item, dict):
            continue
        urn = str(item.get("entityUrn") or "")
        if section_token not in urn.upper():
            continue
        if exclude and exclude.upper() in urn.upper():
            continue
        top = item.get("topComponents") or []
        if len(top) < 2:
            continue
        components = (
            _dig(top[1], "components", "fixedListComponent", "components") or []
        )
        for entry in components:
            entity = _dig(entry, "components", "entityComponent")
            if isinstance(entity, dict):
                entities.append(entity)
    return entities


def _extract_card_text(item: dict[str, Any]) -> str | None:
    top = item.get("topComponents") or []
    for component in top:
        text = _dig(component, "components", "textComponent", "text", "text")
        if text:
            return text
    return None


def _nested_description(entity: dict[str, Any]) -> str | None:
    sub = entity.get("subComponents") or {}
    components = sub.get("components") or []
    for component in components:
        text = _dig(component, "components", "textComponent", "text", "text")
        if text:
            return text
        text = _dig(
            component,
            "components",
            "fixedListComponent",
            "components",
            0,
            "components",
            "textComponent",
            "text",
            "text",
        )
        if text:
            return text
        text = _dig(
            component,
            "components",
            "insightComponent",
            "text",
            "text",
            "text",
        )
        if text:
            return text
    return None


def _picture_url(picture: Any) -> str | None:
    if not picture:
        return None
    if isinstance(picture, str) and picture.startswith("http"):
        return picture
    if not isinstance(picture, dict):
        return None

    # dash shape: displayImageReference.vectorImage.rootUrl + artifacts
    vector = (
        _dig(picture, "displayImageReference", "vectorImage")
        or _dig(picture, "displayImageReferenceResolutionResult", "vectorImage")
        or picture.get("displayImage")
        or picture.get("vectorImage")
        or picture
    )
    if isinstance(vector, str) and vector.startswith("http"):
        return vector
    if not isinstance(vector, dict):
        return None

    root = vector.get("rootUrl")
    artifacts = vector.get("artifacts") or []
    if root and artifacts:
        best = max(
            artifacts,
            key=lambda a: (a.get("width") or 0) if isinstance(a, dict) else 0,
        )
        file_path = best.get("fileIdentifyingUrlPathSegment") if isinstance(best, dict) else None
        if file_path:
            return f"{root}{file_path}"

    # legacy cropped image
    cropped = picture.get("croppedImage") or {}
    if isinstance(cropped, dict):
        return _picture_url(cropped.get("image") or cropped)
    return None


def _date_info(value: Any) -> DateInfo | None:
    if not isinstance(value, dict):
        return None
    year = value.get("year")
    month = value.get("month")
    day = value.get("day")
    if year is None and month is None and day is None:
        return None
    return DateInfo(year=_as_int(year), month=_as_int(month), day=_as_int(day))


def _parse_date_range_text(text: str | None) -> tuple[DateInfo | None, DateInfo | None, bool]:
    if not text:
        return None, None, False
    # e.g. "Jan 2020 - Present · 4 yrs"
    cleaned = text.split("·")[0].strip()
    parts = [p.strip() for p in cleaned.split("-")]
    if len(parts) == 1:
        return _parse_month_year(parts[0]), None, False
    start = _parse_month_year(parts[0])
    end_raw = parts[1]
    if end_raw.lower() == "present":
        return start, None, True
    return start, _parse_month_year(end_raw), False


def _parse_month_year(text: str) -> DateInfo | None:
    months = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }
    tokens = text.strip().split()
    if len(tokens) == 1 and tokens[0].isdigit():
        return DateInfo(year=int(tokens[0]))
    if len(tokens) >= 2:
        month = months.get(tokens[0][:3].lower())
        year = int(tokens[1]) if tokens[1].isdigit() else None
        if month or year:
            return DateInfo(year=year, month=month)
    return None


def _split_degree_field(line: str | None) -> tuple[str | None, str | None]:
    if not line:
        return None, None
    if "," in line:
        left, right = line.split(",", 1)
        return left.strip(), right.strip()
    if "·" in line:
        left, right = line.split("·", 1)
        return left.strip(), right.strip()
    return line.strip(), None


def _elements_by_type(data: dict[str, Any], type_hint: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    hint = type_hint.lower()
    for item in data.get("included") or []:
        if not isinstance(item, dict):
            continue
        type_name = str(item.get("$type") or item.get("entityUrn") or "").lower()
        if hint in type_name:
            results.append(item)
    return results


def _find_included(data: dict[str, Any], urn: str) -> dict[str, Any] | None:
    for item in data.get("included") or []:
        if isinstance(item, dict) and item.get("entityUrn") == urn:
            return item
    return None


def _dig(obj: Any, *path: Any) -> Any:
    cur = obj
    for key in path:
        if isinstance(key, int):
            if not isinstance(cur, list) or key >= len(cur):
                return None
            cur = cur[key]
            continue
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
        if cur is None:
            return None
    return cur


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _first_int(*values: Any) -> int | None:
    for value in values:
        parsed = _as_int(value)
        if parsed is not None:
            return parsed
    return None
