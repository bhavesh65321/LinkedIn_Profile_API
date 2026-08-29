from app.linkedin.exceptions import InvalidProfileUrlError
from app.linkedin.parser import extract_public_identifier


def test_extract_public_identifier_happy_path():
    assert (
        extract_public_identifier("https://www.linkedin.com/in/williamhgates/")
        == "williamhgates"
    )


def test_extract_public_identifier_with_query():
    assert (
        extract_public_identifier("https://linkedin.com/in/jane-doe-123?trk=xyz")
        == "jane-doe-123"
    )


def test_extract_public_identifier_rejects_non_profile():
    try:
        extract_public_identifier("https://www.linkedin.com/company/google/")
        assert False, "expected InvalidProfileUrlError"
    except InvalidProfileUrlError:
        pass
