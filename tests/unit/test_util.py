"""
Unit tests for tg_prompt_api.core.util — pure functions, no DB or network.
"""
import hashlib
import hmac

import pytest

from tg_prompt_api.core.config import settings
from tg_prompt_api.services.prompts.models import parse_prompt_id
from tg_prompt_api.core.util import (
    resolve_callback_url,
    sign_body,
    validate_callback_url,
    validate_media_path,
)
import tg_prompt_api.core.util as util_module


# ---------------------------------------------------------------------------
# parse_prompt_id
# ---------------------------------------------------------------------------


class TestParsePromptId:
    def test_hash_prefix_returns_integer(self):
        assert parse_prompt_id("#123") == 123

    def test_plain_number_string_returns_integer(self):
        assert parse_prompt_id("123") == 123

    def test_empty_string_returns_none(self):
        assert parse_prompt_id("") is None

    def test_hash_only_returns_none(self):
        # "#" with nothing after it cannot be converted to int
        assert parse_prompt_id("#") is None

    def test_hash_with_non_numeric_returns_none(self):
        assert parse_prompt_id("#abc") is None

    def test_hash_zero_is_valid(self):
        # Zero is a valid database row number
        assert parse_prompt_id("#0") == 0

    def test_negative_number_returns_none(self):
        # str.isdigit() returns False for negative strings so "-1" falls through
        assert parse_prompt_id("-1") is None

    def test_plain_alpha_returns_none(self):
        assert parse_prompt_id("abc") is None

    def test_large_number_returns_integer(self):
        assert parse_prompt_id("#99999") == 99999

    def test_hash_with_leading_zero_returns_integer(self):
        # int("#07") → 7; valid, just strips the leading zero
        assert parse_prompt_id("#07") == 7


# ---------------------------------------------------------------------------
# sign_body
# ---------------------------------------------------------------------------


class TestSignBody:
    def test_returns_sha256_prefixed_string(self):
        sig = sign_body(b"hello")
        assert sig.startswith("sha256=")

    def test_deterministic_same_input_same_output(self):
        assert sign_body(b"payload") == sign_body(b"payload")

    def test_different_body_different_signature(self):
        assert sign_body(b"aaa") != sign_body(b"bbb")

    def test_hex_part_is_64_chars(self):
        sig = sign_body(b"test body")
        hex_part = sig[len("sha256="):]
        assert len(hex_part) == 64

    def test_signature_is_valid_hmac_sha256(self):
        body = b"round-trip test body"
        sig = sign_body(body)
        hex_part = sig[len("sha256="):]

        secret = settings.CALLBACK_SIGNING_SECRET.get_secret_value().encode()
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        assert hex_part == expected

    def test_empty_body_does_not_raise(self):
        sig = sign_body(b"")
        assert sig.startswith("sha256=")


# ---------------------------------------------------------------------------
# resolve_callback_url
# ---------------------------------------------------------------------------


class TestResolveCallbackUrl:
    def test_not_in_docker_returns_url_unchanged(self, monkeypatch):
        monkeypatch.setattr(util_module, "_IN_DOCKER", False)
        url = "http://localhost:8110/cb"
        assert resolve_callback_url(url) == url

    def test_in_docker_rewrites_localhost(self, monkeypatch):
        monkeypatch.setattr(util_module, "_IN_DOCKER", True)
        result = resolve_callback_url("http://localhost:8110/cb")
        assert result == "http://host.docker.internal:8110/cb"

    def test_in_docker_rewrites_127_0_0_1(self, monkeypatch):
        monkeypatch.setattr(util_module, "_IN_DOCKER", True)
        result = resolve_callback_url("http://127.0.0.1:9000/cb")
        assert result == "http://host.docker.internal:9000/cb"

    def test_in_docker_external_url_unchanged(self, monkeypatch):
        monkeypatch.setattr(util_module, "_IN_DOCKER", True)
        url = "https://api.example.com/cb"
        assert resolve_callback_url(url) == url

    def test_in_docker_preserves_path_and_query(self, monkeypatch):
        monkeypatch.setattr(util_module, "_IN_DOCKER", True)
        result = resolve_callback_url("http://localhost:8080/path?foo=bar")
        assert result == "http://host.docker.internal:8080/path?foo=bar"


# ---------------------------------------------------------------------------
# validate_callback_url
# ---------------------------------------------------------------------------


class TestValidateCallbackUrl:
    def test_https_public_hostname_is_valid(self):
        # Should not raise
        validate_callback_url("https://api.example.com/cb")

    def test_http_public_hostname_is_valid(self):
        validate_callback_url("http://api.example.com/cb")

    def test_ftp_scheme_raises_value_error(self):
        with pytest.raises(ValueError, match="scheme"):
            validate_callback_url("ftp://api.example.com/cb")

    def test_file_scheme_raises_value_error(self):
        with pytest.raises(ValueError):
            validate_callback_url("file:///etc/passwd")

    def test_private_ip_192_raises_value_error(self):
        with pytest.raises(ValueError):
            validate_callback_url("http://192.168.1.1/cb")

    def test_loopback_127_raises_value_error(self):
        with pytest.raises(ValueError):
            validate_callback_url("http://127.0.0.1/cb")

    def test_private_ip_10_raises_value_error(self):
        with pytest.raises(ValueError):
            validate_callback_url("http://10.0.0.1/cb")

    def test_private_ip_172_16_raises_value_error(self):
        with pytest.raises(ValueError):
            validate_callback_url("http://172.16.0.1/cb")

    def test_link_local_169_254_raises_value_error(self):
        with pytest.raises(ValueError):
            validate_callback_url("http://169.254.1.1/cb")

    def test_hostname_not_ip_is_allowed(self):
        # DNS is not resolved; internal hostnames are permitted
        validate_callback_url("http://internal-server/cb")

    def test_subdomain_hostname_is_allowed(self):
        validate_callback_url("https://hooks.slack.com/services/T123/B456/abc")


# ---------------------------------------------------------------------------
# validate_media_path
# ---------------------------------------------------------------------------


class TestValidateMediaPath:
    def test_media_allowed_dir_none_raises(self, monkeypatch):
        monkeypatch.setattr(settings, "MEDIA_ALLOWED_DIR", None)
        with pytest.raises(ValueError, match="MEDIA_ALLOWED_DIR"):
            validate_media_path("/any/path/file.jpg")

    def test_path_inside_allowed_dir_does_not_raise(self, monkeypatch, tmp_path):
        allowed = str(tmp_path)
        monkeypatch.setattr(settings, "MEDIA_ALLOWED_DIR", allowed)
        valid_path = str(tmp_path / "image.jpg")
        # Should not raise
        validate_media_path(valid_path)

    def test_path_traversal_raises(self, monkeypatch, tmp_path):
        allowed = str(tmp_path / "allowed")
        monkeypatch.setattr(settings, "MEDIA_ALLOWED_DIR", allowed)
        traversal = str(tmp_path / "allowed" / ".." / "secret.txt")
        with pytest.raises(ValueError):
            validate_media_path(traversal)

    def test_completely_outside_dir_raises(self, monkeypatch, tmp_path):
        allowed = str(tmp_path / "media")
        monkeypatch.setattr(settings, "MEDIA_ALLOWED_DIR", allowed)
        outside = "/etc/passwd"
        with pytest.raises(ValueError):
            validate_media_path(outside)
