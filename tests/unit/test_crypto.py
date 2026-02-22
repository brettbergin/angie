"""Tests for crypto helpers (encrypt, decrypt, mask)."""

import pytest

from angie.core.crypto import decrypt_json, encrypt_json, mask_credential, reset_fernet


@pytest.fixture(autouse=True)
def _reset():
    """Ensure a fresh Fernet instance each test."""
    reset_fernet()
    yield
    reset_fernet()


class TestEncryptDecrypt:
    def test_round_trip(self):
        data = {"token": "ghp_abc123", "scope": "repo"}
        cipher = encrypt_json(data)
        assert isinstance(cipher, str)
        assert cipher != str(data)
        result = decrypt_json(cipher)
        assert result == data

    def test_different_data_different_cipher(self):
        a = encrypt_json({"key": "value_a"})
        b = encrypt_json({"key": "value_b"})
        assert a != b

    def test_tampered_cipher_raises(self):
        cipher = encrypt_json({"x": "y"})
        tampered = cipher[:-4] + "ZZZZ"
        with pytest.raises(ValueError, match="Invalid or corrupted"):
            decrypt_json(tampered)

    def test_empty_dict(self):
        cipher = encrypt_json({})
        assert decrypt_json(cipher) == {}


class TestMaskCredential:
    def test_short_value(self):
        assert mask_credential("abc") == "***"

    def test_long_value(self):
        result = mask_credential("ghp_abcdefghijk")
        assert result.endswith("ijk")
        assert "***" in result or result.count("*") >= 4

    def test_empty(self):
        assert mask_credential("") == ""

    def test_four_chars(self):
        result = mask_credential("abcd")
        assert result == "****"
