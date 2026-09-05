import base64
import importlib
import os

import pytest


@pytest.fixture()
def chat_crypto(tmp_path, monkeypatch):
    key = bytes(range(32))
    key_file = tmp_path / "key"
    key_file.write_text(base64.b64encode(key).decode(), encoding="utf-8")
    db_file = tmp_path / "ai3.db"
    monkeypatch.setenv("AI3_DATA_ENCRYPTION_KEY_FILE", str(key_file))
    monkeypatch.setenv("AI3_DB", str(db_file))
    import app.chat_security as module
    module = importlib.reload(module)
    return module, key, db_file


def test_chat_round_trip_and_ciphertext_hides_plaintext(chat_crypto):
    module, _, db_file = chat_crypto
    payload = {"request": {"messages": [{"role": "user", "content": "TOP SECRET CHAT 123"}]}, "response": {"role": "assistant", "content": "PRIVATE ANSWER 456"}}
    nonce, ciphertext = module.encrypt_json(payload, principal_id=7, conversation_id="conv-a")
    assert b"TOP SECRET CHAT 123" not in ciphertext
    assert b"PRIVATE ANSWER 456" not in ciphertext
    assert module.decrypt_json(nonce, ciphertext, principal_id=7, conversation_id="conv-a") == payload


def test_wrong_key_cannot_decrypt(chat_crypto, monkeypatch, tmp_path):
    module, _, _ = chat_crypto
    nonce, ciphertext = module.encrypt_json({"secret": "abc"}, principal_id=1, conversation_id="conv")
    wrong = tmp_path / "wrong-key"
    wrong.write_text(("ff" * 32), encoding="utf-8")
    monkeypatch.setenv("AI3_DATA_ENCRYPTION_KEY_FILE", str(wrong))
    module = importlib.reload(module)
    with pytest.raises(Exception):
        module.decrypt_json(nonce, ciphertext, principal_id=1, conversation_id="conv")


def test_tampering_is_detected(chat_crypto):
    module, _, _ = chat_crypto
    nonce, ciphertext = module.encrypt_json({"secret": "abc"}, principal_id=1, conversation_id="conv")
    tampered = bytearray(ciphertext)
    tampered[-1] ^= 1
    with pytest.raises(Exception):
        module.decrypt_json(nonce, bytes(tampered), principal_id=1, conversation_id="conv")
