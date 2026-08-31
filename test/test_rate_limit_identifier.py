"""The rate limiter reads `sub` off the bearer token to bucket per user.

It needs its own coverage because the decode there is unlike every other one
in the codebase: `key` is a required positional even when the signature is not
checked, and `verify_aud` has to be disabled or the `aud` claim rejects the
token. Both mistakes were live at once, and the surrounding
`except Exception: pass` hid them — so rate limiting silently bucketed every
caller by IP instead of by user, and everyone behind one NAT shared a bucket.
"""

import pytest
from jose import jwt

from app.config import settings
from app.services.auth import create_access_token


class TestRateLimitTokenRead:
    def test_sub_is_readable_without_verification(self):
        token = create_access_token("user_123")

        payload = jwt.decode(
            token,
            "",
            algorithms=[settings.algorithm],
            options={"verify_signature": False, "verify_aud": False},
        )

        assert payload["sub"] == "user_123"

    def test_key_is_positional_even_when_the_signature_is_skipped(self):
        """Omitting it raises TypeError, which the caller's bare except hid."""
        token = create_access_token("user_123")

        with pytest.raises(TypeError):
            jwt.decode(token, options={"verify_signature": False})

    def test_aud_must_be_skipped_too(self):
        """Tokens carry an `aud`, so leaving verify_aud on rejects them here."""
        token = create_access_token("user_123")

        with pytest.raises(Exception):
            jwt.decode(
                token,
                "",
                algorithms=[settings.algorithm],
                options={"verify_signature": False},
            )


class TestIdentifierResolution:
    """End result: an authenticated caller buckets by user, not by IP."""

    def _request(self, headers):
        class _Client:
            host = "127.0.0.1"

        class _Request:
            def __init__(self, headers):
                self.headers = headers
                self.client = _Client()

        return _Request(headers)

    def test_bearer_token_buckets_by_user(self):
        from app.rate_limit.dependencies import _resolve_identifier

        token = create_access_token("user_abc")
        request = self._request({"authorization": f"Bearer {token}"})

        assert _resolve_identifier(request, "user") == "user:user_abc"

    def test_falls_back_to_ip_without_a_token(self):
        from app.rate_limit.dependencies import _resolve_identifier

        request = self._request({})

        assert _resolve_identifier(request, "user") == "ip:127.0.0.1"
