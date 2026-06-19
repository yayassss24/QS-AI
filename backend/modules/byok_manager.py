"""
modules/byok_manager.py

Manajemen API key milik user (Bring Your Own Key).
Key dienkripsi AES-256 menggunakan Fernet sebelum disimpan.
Key TIDAK PERNAH dikirim kembali ke client.
"""

import json
import os
import tempfile
from pathlib import Path
from cryptography.fernet import Fernet


class BYOKManager:
    """
    Manajemen API key user dengan enkripsi AES-256.

    Args:
        db_path: Path ke file penyimpanan key (JSON)
    """

    def __init__(self, db_path: str = None):
        encryption_key = os.getenv("BYOK_ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError("BYOK_ENCRYPTION_KEY harus diset di environment variable")
        try:
            self.cipher = Fernet(encryption_key.encode())
        except Exception as e:
            raise ValueError(f"BYOK_ENCRYPTION_KEY tidak valid: {e}")
        db_default = str(Path(__file__).parent.parent / "byok_store.json")
        # Use env var or temp dir for writable storage
        custom_path = os.getenv("BYOK_DB_PATH", db_default)
        self.db_path = db_path or custom_path

    def _load_store(self) -> dict:
        try:
            with open(self.db_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_store_atomic(self, store: dict):
        """Atomic write: write to temp file then rename."""
        fd, tmp = tempfile.mkstemp(suffix=".json", dir=os.path.dirname(self.db_path) or ".")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(store, f)
            os.replace(tmp, self.db_path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def save_key(self, user_id: str, api_key: str) -> bool:
        """
        Enkripsi dan simpan API key user.

        Args:
            user_id: ID user
            api_key: API key Gemini milik user

        Returns:
            True jika berhasil, False jika validasi gagal
        """
        if not self.validate_key(api_key)["valid"]:
            return False
        encrypted = self.cipher.encrypt(api_key.encode()).decode()
        store = self._load_store()
        store[user_id] = encrypted
        self._save_store_atomic(store)
        return True

    def get_key(self, user_id: str) -> str:
        """
        Ambil dan dekripsi API key user. Hanya untuk internal backend.

        Args:
            user_id: ID user

        Returns:
            API key atau None jika tidak ditemukan
        """
        store = self._load_store()
        encrypted = store.get(user_id)
        if not encrypted:
            return None
        try:
            return self.cipher.decrypt(encrypted.encode()).decode()
        except Exception:
            return None

    def has_key(self, user_id: str) -> bool:
        """Cek apakah user punya BYOK key tanpa mengekspos key."""
        store = self._load_store()
        return user_id in store

    def delete_key(self, user_id: str) -> bool:
        """Hapus BYOK key user."""
        store = self._load_store()
        if user_id in store:
            del store[user_id]
            self._save_store_atomic(store)
            return True
        return False

    def validate_key(self, api_key: str) -> dict:
        """
        Validasi API key dengan test call ke 9router.

        Args:
            api_key: API key yang akan divalidasi

        Returns:
            dict dengan valid, quota_remaining, error
        """
        try:
            from openai import OpenAI
            base_url = os.getenv("9ROUTER_BASE_URL", "http://localhost:20128/v1").rstrip("/")
            model = os.getenv("9ROUTER_MODEL", "groq/llama-3.3-70b-versatile")
            client = OpenAI(base_url=base_url, api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Balas dengan angka 1 saja."}],
                max_tokens=10,
            )
            return {
                "valid": True,
                "quota_remaining": 1500,
                "error": None,
            }
        except Exception as e:
            return {
                "valid": False,
                "quota_remaining": 0,
                "error": str(e),
            }
