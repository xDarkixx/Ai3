import os
from pathlib import Path


def test_ai3_pki_generates_encrypted_ca(tmp_path, monkeypatch):
    key_file = tmp_path / "data.key"
    key_file.write_bytes(os.urandom(32))
    import app.pki as pki
    monkeypatch.setattr(pki, "PKI_DIR", tmp_path / "pki")
    monkeypatch.setattr(pki, "KEY_FILE", tmp_path / "pki" / "ca.key.enc")
    monkeypatch.setattr(pki, "CERT_FILE", tmp_path / "pki" / "ca.crt")
    monkeypatch.setattr(pki, "ENC_KEY_FILE", str(key_file))
    pki.ensure_ca()
    assert pki.KEY_FILE.exists()
    assert pki.CERT_FILE.exists()
    assert pki.KEY_FILE.read_bytes() != key_file.read_bytes()
    ca_key, ca_cert = pki.ca_objects()
    assert ca_cert.subject == ca_cert.issuer
    assert ca_cert.extensions.get_extension_for_class(pki.x509.BasicConstraints).value.ca is True
    assert ca_key is not None


def test_ai3_verification_encryption_round_trip(tmp_path, monkeypatch):
    key_file = tmp_path / "data.key"
    key_file.write_bytes(os.urandom(32))
    import app.own_verification as verification
    monkeypatch.setattr(verification, "KEY_FILE", str(key_file))
    aad = b"AI3-VERIFICATION:1"
    plaintext = b"private verification evidence"
    ciphertext = verification.enc(plaintext, aad)
    assert ciphertext != plaintext
    assert verification.dec(ciphertext, aad) == plaintext
