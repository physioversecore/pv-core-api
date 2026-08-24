"""Round-trip tests for access tokens.

These exist because of a real outage: `create_access_token` was changed to emit
`iss`/`aud` claims while the `jwt.decode` calls kept their old signature. Since
python-jose rejects a token carrying `aud` unless the expected audience is
supplied, every authenticated request started returning 401 "Invalid token" —
and no test caught it, because encode and decode were only ever tested apart.

Anything that decodes a token belongs here.
"""

from datetime import datetime, timedelta, timezone

import pytest
from jose import JWTError, jwt

from app.config import settings
from app.services.auth import create_access_token, decode_access_token


class TestTokenRoundTrip:
    def test_a_freshly_issued_token_decodes(self):
        """The regression itself: issue a token, then accept it."""
        token = create_access_token("user_123")
        payload = decode_access_token(token)
        assert payload["sub"] == "user_123"

    def test_role_claim_survives_the_round_trip(self):
        token = create_access_token("user_123", role="THERAPIST")
        assert decode_access_token(token)["role"] == "therapist"

    def test_issued_token_carries_the_claims_the_decoder_expects(self):
        payload = decode_access_token(create_access_token("user_123"))
        assert payload["iss"] == settings.jwt_issuer
        assert payload["aud"] == settings.jwt_audience
        assert "iat" in payload and "exp" in payload


class TestTokenRejection:
    def _token(self, *, key=None, iss=None, aud=None, minutes=60):
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": "user_123",
                "exp": now + timedelta(minutes=minutes),
                "iat": now,
                "iss": iss or settings.jwt_issuer,
                "aud": aud or settings.jwt_audience,
            },
            key or settings.secret_key,
            algorithm=settings.algorithm,
        )

    def test_rejects_a_forged_signature(self):
        with pytest.raises(JWTError):
            decode_access_token(self._token(key="not-the-secret"))

    def test_rejects_another_audience(self):
        with pytest.raises(JWTError):
            decode_access_token(self._token(aud="some-other-app"))

    def test_rejects_another_issuer(self):
        with pytest.raises(JWTError):
            decode_access_token(self._token(iss="some-other-app"))

    def test_rejects_an_expired_token(self):
        with pytest.raises(JWTError):
            decode_access_token(self._token(minutes=-1))

    def test_expiry_can_be_skipped_for_request_logging(self):
        """Access logging identifies the caller even on an expired token."""
        payload = decode_access_token(self._token(minutes=-1), verify_exp=False)
        assert payload["sub"] == "user_123"


class TestRateLimitKeyExtraction:
    """The rate limiter reads `sub` without verifying anything.

    It needs its own coverage: `key` is a required positional even when the
    signature is not checked, and `verify_aud` has to be disabled or the aud
    claim rejects the token here too. Both mistakes were live at once, and the
    surrounding `except Exception: pass` hid them — rate limiting silently
    bucketed everyone by IP instead of by user.
    """

    def test_sub_is_readable_without_verification(self):
        token = create_access_token("user_123")
        payload = jwt.decode(
            token,
            "",
            algorithms=[settings.algorithm],
            options={"verify_signature": False, "verify_aud": False},
        )
        assert payload["sub"] == "user_123"
