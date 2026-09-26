import pytest
from pydantic import ValidationError

# Import the Settings class from the backend module.
from backend.app.config import Settings


def test_settings_valid_creation():
    """Creating Settings with valid data should succeed."""
    settings = Settings(
        navidrome_url="http://example.com",
        navidrome_user="user",
        navidrome_password="secret",
        navidrome_timeout_seconds=10,
        dwe_artist="Test Artist",
    )
    assert settings.navidrome_url.host == "example.com"
    assert settings.navidrome_timeout_seconds == 10


@pytest.mark.parametrize(
    "timeout", [0, -5]
)
def test_settings_invalid_timeout(timeout):
    """Timeout must be greater than 0; invalid values raise ValidationError."""
    with pytest.raises(ValidationError):
        Settings(
            navidrome_url="http://example.com",
            navidrome_user="user",
            navidrome_password="secret",
            navidrome_timeout_seconds=timeout,
            dwe_artist="Test Artist",
        )


def test_settings_invalid_url():
    """Malformed URL should cause ValidationError."""
    with pytest.raises(ValidationError):
        Settings(
            navidrome_url="not-a-valid-url",
            navidrome_user="user",
            navidrome_password="secret",
            navidrome_timeout_seconds=10,
            dwe_artist="Test Artist",
        )

def test_settings_multiple_artists():
    """Settings should accept multiple artists in the list."""
    settings = Settings(
        navidrome_url="http://example.com",
        navidrome_user="user",
        navidrome_password="secret",
        navidrome_timeout_seconds=10,
        dwe_artist="Artist One",
    )
    assert settings.dwe_artist == "Artist One"
