"""Forked job processes never reuse the parent's database connections (#56).

RQ forks a work horse per job. A child that reuses the parent's pooled connection
shares its server session, and psycopg's auto-prepared statements then collide
("prepared statement _pg3_0 already exists") after a few jobs.
"""

import os
from collections.abc import Iterator

import pytest

from app import db
from app.config import get_settings


@pytest.fixture
def engine_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # create_engine never connects until first use, so no database is needed.
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@127.0.0.1:1/unused")
    monkeypatch.setenv("VALKEY_URL", "redis://unused")
    get_settings.cache_clear()
    db.get_engine.cache_clear()
    yield
    db.get_engine.cache_clear()
    get_settings.cache_clear()


def test_a_forked_child_gets_a_fresh_connection_pool(engine_settings: None) -> None:
    parent_pool = id(db.get_engine().pool)
    read, write = os.pipe()
    pid = os.fork()
    if pid == 0:  # child: report whether it still holds the parent's pool, then leave
        os.close(read)
        os.write(write, b"fresh" if id(db.get_engine().pool) != parent_pool else b"shared")
        os._exit(0)
    os.close(write)
    answer = os.read(read, 16)
    os.close(read)
    os.waitpid(pid, 0)
    assert answer == b"fresh"
    assert id(db.get_engine().pool) == parent_pool  # the parent keeps its own pool


def test_the_fork_hook_does_not_create_an_engine(engine_settings: None) -> None:
    db._forget_inherited_connections()
    assert db.get_engine.cache_info().currsize == 0
