import pytest
from manifest_signer.errors import KeyMismatchError, SignerError, VerificationError


def test_signer_error_is_exception():
    assert issubclass(SignerError, Exception)


def test_key_mismatch_error_is_signer_error():
    assert issubclass(KeyMismatchError, SignerError)


def test_verification_error_is_exception():
    assert issubclass(VerificationError, Exception)


def test_raising_key_mismatch_carries_message():
    with pytest.raises(KeyMismatchError, match="bad key"):
        raise KeyMismatchError("bad key")
