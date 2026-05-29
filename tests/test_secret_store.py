from pathlib import Path

import pytest

from paper_writer_agent.secret_store import SecretStore, SecretStoreError


def test_secret_store_encrypts_api_key_without_plaintext(tmp_path):
    secret_path = tmp_path / "seed2.enc.json"
    store = SecretStore(secret_path)

    store.save_api_key(api_key="secret-api-key", pin="123456")

    encrypted_text = secret_path.read_text(encoding="utf-8")
    assert "secret-api-key" not in encrypted_text
    assert "123456" not in encrypted_text
    assert store.load_api_key(pin="123456") == "secret-api-key"


def test_secret_store_rejects_wrong_pin(tmp_path):
    secret_path = tmp_path / "seed2.enc.json"
    store = SecretStore(secret_path)
    store.save_api_key(api_key="secret-api-key", pin="123456")

    with pytest.raises(SecretStoreError):
        store.load_api_key(pin="000000")
