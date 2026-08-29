from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


class DateInfo(BaseModel):
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None


class ExperienceItem(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    company_url: Optional[str] = None
    company_linkedin_id: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    employment_type: Optional[str] = None
    start_date: Optional[DateInfo] = None
    end_date: Optional[DateInfo] = None
    is_current: bool = False


class EducationItem(BaseModel):
    school: Optional[str] = None
    school_url: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[DateInfo] = None
    end_date: Optional[DateInfo] = None


class SkillItem(BaseModel):
    name: str
    endorsements: Optional[int] = None


class CertificationItem(BaseModel):
    name: Optional[str] = None
    authority: Optional[str] = None
    license_number: Optional[str] = None
    url: Optional[str] = None
    issued_at: Optional[DateInfo] = None
    expires_at: Optional[DateInfo] = None


class LanguageItem(BaseModel):
    name: str
    proficiency: Optional[str] = None


class ProfileRequest(BaseModel):
    url: str = Field(
        ...,
        description="LinkedIn profile URL, e.g. https://www.linkedin.com/in/williamhgates/",
        examples=["https://www.linkedin.com/in/williamhgates/"],
    )


class ProfileResponse(BaseModel):
    url: str
    public_identifier: str
    profile_urn: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    about: Optional[str] = None
    profile_picture: Optional[str] = None
    background_image: Optional[str] = None
    follower_count: Optional[int] = None
    connection_count: Optional[int] = None
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    skills: List[SkillItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)
    languages: List[LanguageItem] = Field(default_factory=list)
    scraped_at: datetime


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    linkedin_credentials_configured: bool
    linkedin_session_ok: Optional[bool] = None
    detail: Optional[str] = None
    extras: Optional[Dict[str, Any]] = None


class ProfileUrlQuery(BaseModel):
    url: HttpUrl
