import pytest
from argparse import Namespace
from faaster.cli.cli import _post_validate, _infer_backend, DatabaseBackend
from faaster.security.server_security import SecurityPolicy, SecurityMode


def _base_namespace(**overrides):
    defaults = dict(
        url_database=None,
        db_backend=None,
        pki_dir=None,
        security_policy=None,
        auto_accept_clients=False,
    )
    defaults.update(overrides)
    return Namespace(**defaults)


# ------------------------------------------------------------------
# Database backend inference
# ------------------------------------------------------------------

def test_no_db_args_passes():
    ns = _base_namespace()
    _post_validate(ns)
    assert ns.db_backend is None


def test_infers_mongodb_from_url():
    ns = _base_namespace(url_database="mongodb://localhost:27017")
    _post_validate(ns)
    assert ns.db_backend == DatabaseBackend.mongodb


def test_infers_timescaledb_from_postgresql():
    ns = _base_namespace(url_database="postgresql://user:pass@localhost:5432/db")
    _post_validate(ns)
    assert ns.db_backend == DatabaseBackend.timescaledb


def test_infers_timescaledb_from_postgres():
    ns = _base_namespace(url_database="postgres://localhost/db")
    _post_validate(ns)
    assert ns.db_backend == DatabaseBackend.timescaledb


def test_db_backend_without_url_raises():
    ns = _base_namespace(db_backend=DatabaseBackend.mongodb)
    with pytest.raises(SystemExit, match="--db-backend requires --url-database"):
        _post_validate(ns)


def test_unknown_url_scheme_raises():
    with pytest.raises(SystemExit, match="could not infer database backend"):
        _infer_backend("redis://localhost:6379")


# ------------------------------------------------------------------
# Security cross-validation
# ------------------------------------------------------------------

def test_security_policy_without_pki_dir_raises():
    ns = _base_namespace(security_policy=[SecurityPolicy.basic256], pki_dir=None)
    with pytest.raises(SystemExit, match="--security-policy requires --pki-dir"):
        _post_validate(ns)


def test_security_policy_with_pki_dir_passes():
    ns = _base_namespace(security_policy=[SecurityPolicy.basic256], pki_dir="/tmp/pki")
    _post_validate(ns)


def test_auto_accept_without_pki_dir_raises():
    ns = _base_namespace(auto_accept_clients=True, pki_dir=None)
    with pytest.raises(SystemExit, match="--auto-accept-clients requires --pki-dir"):
        _post_validate(ns)


def test_auto_accept_without_security_policy_raises():
    ns = _base_namespace(auto_accept_clients=True, pki_dir="/tmp/pki", security_policy=None)
    with pytest.raises(SystemExit, match="--auto-accept-clients only makes sense with --security-policy"):
        _post_validate(ns)


def test_auto_accept_with_pki_and_policy_passes():
    ns = _base_namespace(
        auto_accept_clients=True,
        pki_dir="/tmp/pki",
        security_policy=[SecurityPolicy.aes128],
    )
    _post_validate(ns)


def test_no_security_args_passes():
    ns = _base_namespace()
    _post_validate(ns)
