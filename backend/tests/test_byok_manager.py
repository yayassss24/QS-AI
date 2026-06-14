"""Tests for byok_manager.py"""

import os
import json
import tempfile
from unittest.mock import patch

import pytest

from modules.byok_manager import BYOKManager


class TestBYOKManagerInit:
    def test_requires_encryption_key(self):
        if "BYOK_ENCRYPTION_KEY" in os.environ:
            del os.environ["BYOK_ENCRYPTION_KEY"]
        with pytest.raises(ValueError, match="BYOK_ENCRYPTION_KEY"):
            BYOKManager()

    def test_initializes_with_key(self, fernet_key):
        os.environ["BYOK_ENCRYPTION_KEY"] = fernet_key
        manager = BYOKManager(db_path=tempfile.mktemp(suffix=".json"))
        assert manager.cipher is not None


class TestBYOKKeyManagement:
    @pytest.fixture(autouse=True)
    def setup(self, fernet_key):
        os.environ["BYOK_ENCRYPTION_KEY"] = fernet_key
        self.db_path = tempfile.mktemp(suffix=".json")
        self.manager = BYOKManager(db_path=self.db_path)
        yield
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    @patch.object(BYOKManager, "validate_key", return_value={"valid": True, "quota_remaining": 1500, "error": None})
    def test_save_and_get_key(self, mock_validate):
        saved = self.manager.save_key("user1", "AIza-test-key")
        assert saved is True
        key = self.manager.get_key("user1")
        assert key == "AIza-test-key"

    @patch.object(BYOKManager, "validate_key", return_value={"valid": True, "quota_remaining": 1500, "error": None})
    def test_store_is_encrypted(self, mock_validate):
        self.manager.save_key("user1", "AIza-test-key-12345")
        assert os.path.exists(self.db_path)
        with open(self.db_path) as f:
            store = json.load(f)
        encrypted = store.get("user1")
        assert encrypted is not None
        assert "AIza" not in encrypted
        assert "test-key" not in encrypted
        # Verifikasi bisa didekripsi
        decrypted = self.manager.get_key("user1")
        assert decrypted == "AIza-test-key-12345"

    def test_has_key_returns_false_for_unknown(self):
        assert self.manager.has_key("nonexistent") is False

    @patch.object(BYOKManager, "validate_key", return_value={"valid": True, "quota_remaining": 1500, "error": None})
    def test_has_key_returns_true_after_save(self, mock_validate):
        self.manager.save_key("user2", "AIza-key")
        assert self.manager.has_key("user2") is True

    def test_delete_key(self):
        assert self.manager.delete_key("nonexistent") is False

    @patch.object(BYOKManager, "validate_key", return_value={"valid": True, "quota_remaining": 1500, "error": None})
    def test_delete_key_after_save(self, mock_validate):
        self.manager.save_key("user3", "AIza-key")
        assert self.manager.delete_key("user3") is True
        assert self.manager.has_key("user3") is False

    def test_get_key_returns_none_for_unknown(self):
        assert self.manager.get_key("nonexistent") is None

    def test_save_invalid_key_returns_false(self):
        result = self.manager.save_key("user1", "bad-key")
        assert result is False


class TestBYOKValidateKey:
    @pytest.fixture(autouse=True)
    def setup(self, fernet_key):
        os.environ["BYOK_ENCRYPTION_KEY"] = fernet_key
        self.manager = BYOKManager(db_path=tempfile.mktemp(suffix=".json"))

    def test_validate_response_keys(self):
        result = self.manager.validate_key("test")
        assert "valid" in result
        assert "quota_remaining" in result
        assert "error" in result
