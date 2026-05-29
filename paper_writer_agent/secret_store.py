from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class SecretStoreError(Exception):
    pass


class SecretStore:
    def __init__(self, path: Path, iterations: int = 390_000):
        self.path = path
        self.iterations = iterations

    def save_api_key(self, api_key: str, pin: str) -> None:
        if not api_key.strip():
            raise SecretStoreError("API key cannot be empty.")
        if not pin:
            raise SecretStoreError("PIN cannot be empty.")

        salt = os.urandom(16)
        fernet = Fernet(_derive_key(pin=pin, salt=salt, iterations=self.iterations))
        token = fernet.encrypt(api_key.encode("utf-8"))
        payload = {
            "version": 1,
            "kdf": "pbkdf2-hmac-sha256",
            "iterations": self.iterations,
            "salt": base64.urlsafe_b64encode(salt).decode("ascii"),
            "token": token.decode("ascii"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_api_key(self, pin: str) -> str:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            salt = base64.urlsafe_b64decode(payload["salt"].encode("ascii"))
            token = payload["token"].encode("ascii")
            iterations = int(payload["iterations"])
        except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise SecretStoreError("Encrypted credential file is missing or invalid.") from exc

        fernet = Fernet(_derive_key(pin=pin, salt=salt, iterations=iterations))
        try:
            return fernet.decrypt(token).decode("utf-8")
        except InvalidToken as exc:
            raise SecretStoreError("Unable to decrypt API key. Check the PIN.") from exc


def _derive_key(pin: str, salt: bytes, iterations: int) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(pin.encode("utf-8")))
