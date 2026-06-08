from __future__ import annotations

from unittest.mock import MagicMock

from demo.sessions import (
    ABSA_ACCOUNT_ID,
    LS_ENDPOINT,
    PRODUCER_ACCOUNT_ID,
    absa_session,
    producer_session,
)


def test_ls_endpoint_constant_is_local_4566() -> None:
    """The single source of truth for LocalStack's endpoint URL."""
    assert LS_ENDPOINT == "http://localhost:4566"


def test_account_id_constants() -> None:
    """Account IDs are deterministic per spec §4.2."""
    assert PRODUCER_ACCOUNT_ID == "111111111111"
    assert ABSA_ACCOUNT_ID == "222222222222"


def test_producer_session_uses_test_credentials() -> None:
    """Producer session uses LocalStack test credentials."""
    sess = producer_session()
    creds = sess.get_credentials()
    assert creds.access_key == "test"
    assert creds.secret_key == "test"
    assert sess.region_name == "eu-west-1"


def test_absa_session_uses_test_credentials() -> None:
    """ABSA session uses the same test credentials but different header injection."""
    sess = absa_session()
    creds = sess.get_credentials()
    assert creds.access_key == "test"
    assert creds.secret_key == "test"


def test_producer_session_injects_111_account_header() -> None:
    """The before-sign hook on producer_session injects 111111111111 header."""
    sess = producer_session()
    request = MagicMock()
    request.headers = {}
    # signature_version=None mirrors what botocore's signing chain passes in
    # production — it's required by a builtin before-sign.s3 handler. Without
    # it the builtin crashes before our hook runs.
    sess.events.emit("before-sign.s3.PutObject", request=request, signature_version=None)
    assert request.headers.get("x-localstack-account-id") == PRODUCER_ACCOUNT_ID


def test_absa_session_injects_222_account_header() -> None:
    """The before-sign hook on absa_session injects 222222222222 header."""
    sess = absa_session()
    request = MagicMock()
    request.headers = {}
    sess.events.emit("before-sign.s3.GetObject", request=request, signature_version=None)
    assert request.headers.get("x-localstack-account-id") == ABSA_ACCOUNT_ID


def test_different_sessions_have_independent_header_hooks() -> None:
    """Producer and ABSA hooks don't leak across sessions — critical for
    cross-account boundary correctness.
    """
    p_sess = producer_session()
    a_sess = absa_session()
    p_req = MagicMock()
    p_req.headers = {}
    a_req = MagicMock()
    a_req.headers = {}
    p_sess.events.emit("before-sign.kms.Sign", request=p_req)
    a_sess.events.emit("before-sign.s3.GetObject", request=a_req, signature_version=None)
    assert p_req.headers["x-localstack-account-id"] == "111111111111"
    assert a_req.headers["x-localstack-account-id"] == "222222222222"
