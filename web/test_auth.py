"""Tests for web.auth — operator passcode, sessions, rate limit, open mode.

    python -m pytest web/test_auth.py -q
"""

from __future__ import annotations

import hmac
import os
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from web import auth  # noqa: E402


class AuthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        auth.reset_state()
        self._env_backup = os.environ.get(auth.ENV_HASH)
        os.environ.pop(auth.ENV_HASH, None)
        # Ensure we do not pick up a real operator.txt during tests.
        self._file_patch = mock.patch.object(
            auth, "OPERATOR_FILE", Path("/nonexistent/operator.txt")
        )
        self._file_patch.start()
        auth.reload_config()

    def tearDown(self) -> None:
        self._file_patch.stop()
        if self._env_backup is None:
            os.environ.pop(auth.ENV_HASH, None)
        else:
            os.environ[auth.ENV_HASH] = self._env_backup
        auth.reset_state()
        auth.reload_config()

    def _configure_hash(self, password: str) -> str:
        digest = auth.hash_passcode(password)
        os.environ[auth.ENV_HASH] = digest
        auth.reload_config()
        self.assertFalse(auth.is_open_mode())
        return digest


class TestOpenMode(AuthTestCase):
    def test_open_mode_when_no_hash(self) -> None:
        self.assertTrue(auth.is_open_mode())
        self.assertFalse(auth.verify_passcode("anything"))
        self.assertFalse(auth.verify_passcode(""))


class TestPasscode(AuthTestCase):
    def test_wrong_rejected(self) -> None:
        self._configure_hash("correct-horse")
        self.assertFalse(auth.verify_passcode("wrong-battery"))
        self.assertFalse(auth.verify_passcode(""))
        self.assertFalse(auth.verify_passcode("correct-hors"))

    def test_right_accepted(self) -> None:
        self._configure_hash("correct-horse")
        self.assertTrue(auth.verify_passcode("correct-horse"))

    def test_pbkdf2_format_and_iterations(self) -> None:
        # Force PBKDF2 path regardless of argon2 availability.
        with mock.patch.object(auth, "_HAS_ARGON2", False), mock.patch.object(
            auth, "_ARGON2", None
        ):
            digest = auth.hash_passcode("secret")
        self.assertTrue(digest.startswith(f"{auth.PBKDF2_PREFIX}$"))
        parts = digest.split("$")
        self.assertEqual(len(parts), 4)
        self.assertGreaterEqual(int(parts[1]), 600_000)

        os.environ[auth.ENV_HASH] = digest
        auth.reload_config()
        self.assertTrue(auth.verify_passcode("secret"))
        self.assertFalse(auth.verify_passcode("Secret"))


class TestTimingSafeCompare(AuthTestCase):
    def test_module_exposes_compare_digest(self) -> None:
        self.assertIs(auth.compare_digest, hmac.compare_digest)

    def test_pbkdf2_uses_compare_digest(self) -> None:
        with mock.patch.object(auth, "_HAS_ARGON2", False), mock.patch.object(
            auth, "_ARGON2", None
        ):
            digest = auth.hash_passcode("alpha")
        os.environ[auth.ENV_HASH] = digest
        auth.reload_config()

        calls: list[tuple[bytes, bytes]] = []
        real = hmac.compare_digest

        def spy(a: bytes | str, b: bytes | str) -> bool:
            if isinstance(a, (bytes, bytearray)) and isinstance(b, (bytes, bytearray)):
                calls.append((bytes(a), bytes(b)))
            return real(a, b)

        with mock.patch.object(auth.hmac, "compare_digest", side_effect=spy):
            self.assertTrue(auth.verify_passcode("alpha"))
            self.assertFalse(auth.verify_passcode("bravo"))
        self.assertGreaterEqual(len(calls), 2)

    def test_wrong_lengths_still_reject(self) -> None:
        self._configure_hash("medium-length-pass")
        for guess in ("x", "y" * 200, "medium-length-pas"):
            self.assertFalse(auth.verify_passcode(guess))


class TestSessionCookie(AuthTestCase):
    def test_cookie_required_semantics(self) -> None:
        self.assertFalse(auth.validate_session(None))
        self.assertFalse(auth.validate_session(""))
        self.assertFalse(auth.validate_session("not-a-real-token"))

        token = auth.create_session()
        self.assertTrue(auth.validate_session(token))

        auth.clear_session(token)
        self.assertFalse(auth.validate_session(token))

    def test_set_cookie_flags(self) -> None:
        token = auth.create_session()
        header = auth.session_cookie_header(token)
        self.assertIn("HttpOnly", header)
        self.assertIn(f"SameSite={auth.COOKIE_SAMESITE}", header)
        self.assertIn(f"{auth.COOKIE_NAME}={token}", header)
        self.assertNotIn("SameSite=None", header)

    def test_token_is_32_random_bytes_encoded(self) -> None:
        token = auth.create_session()
        # token_urlsafe(32) → 43 chars without padding typically
        self.assertGreaterEqual(len(token), 40)

    def test_idle_timeout(self) -> None:
        token = auth.create_session()
        with mock.patch.object(auth, "IDLE_TIMEOUT_S", 0.05):
            self.assertTrue(auth.validate_session(token))
            time.sleep(0.08)
            self.assertFalse(auth.validate_session(token))

    def test_parse_session_cookie(self) -> None:
        token = auth.create_session()
        header = f"other=1; {auth.COOKIE_NAME}={token}; path=/"
        self.assertEqual(auth.parse_session_cookie(header), token)
        self.assertIsNone(auth.parse_session_cookie(None))
        self.assertIsNone(auth.parse_session_cookie("a=b"))


class TestRateLimit(AuthTestCase):
    def test_rate_limiter_trips(self) -> None:
        ip = "203.0.113.9"
        for _ in range(auth.RATE_LIMIT_MAX):
            self.assertTrue(auth.check_rate_limit(ip))
        self.assertFalse(auth.check_rate_limit(ip))
        # Other IPs unaffected.
        self.assertTrue(auth.check_rate_limit("203.0.113.10"))


if __name__ == "__main__":
    unittest.main()
