"""Redis TTL configuration regression; actual backend TTL remains integration acceptance."""

from app.config import get_settings
from app.graph.checkpointer import _redis_ttl_config


def test_sliding_ttl_minutes(monkeypatch):
    monkeypatch.setattr(get_settings(), "checkpoint_ttl_days", 7)
    assert _redis_ttl_config() == {"default_ttl": 10080, "refresh_on_read": True}


def test_disabled_ttl(monkeypatch):
    monkeypatch.setattr(get_settings(), "checkpoint_ttl_days", 0)
    assert _redis_ttl_config() is None
