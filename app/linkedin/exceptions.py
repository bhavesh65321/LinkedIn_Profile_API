class LinkedInError(Exception):
    """Base error for LinkedIn Voyager interactions."""

    def __init__(self, message: str, code: str = "linkedin_error", status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class LinkedInAuthError(LinkedInError):
    def __init__(self, message: str = "LinkedIn session is invalid or expired"):
        super().__init__(message, code="linkedin_auth_error", status_code=502)


class LinkedInNotFoundError(LinkedInError):
    def __init__(self, message: str = "LinkedIn profile not found"):
        super().__init__(message, code="profile_not_found", status_code=404)


class LinkedInRateLimitError(LinkedInError):
    def __init__(self, message: str = "LinkedIn rate limited this request"):
        super().__init__(message, code="linkedin_rate_limited", status_code=429)


class InvalidProfileUrlError(LinkedInError):
    def __init__(self, message: str = "Invalid LinkedIn profile URL"):
        super().__init__(message, code="invalid_url", status_code=400)


class CredentialsMissingError(LinkedInError):
    def __init__(self, message: str = "LI_AT and JSESSIONID must be configured"):
        super().__init__(message, code="credentials_missing", status_code=503)
