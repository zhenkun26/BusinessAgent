"""生产配置强校验(config 加固)"""

from __future__ import annotations

import pytest

from app.config import Settings, validate_production_settings


def test_should_flag_default_secrets_in_production():
    """Given 生产模式且使用代码默认凭证, When 配置校验,
    Then 返回全部违规项(默认 JWT 密钥/数据库口令/短密钥)"""
    settings = Settings(
        app_env="prod",
        jwt_secret_key="change-me-in-production",
        postgres_password="wJ6pbV5eBkzMT2AYDT9w2i8V",
        redis_password="V5lOkygYvgaD6ZZ8rmqJAcO7",
        milvus_password="Milvus123",
        cors_allow_origins="http://localhost:8000",
    )

    violations = validate_production_settings(settings)

    assert any("jwt_secret_key" in v for v in violations)
    assert any("postgres_password" in v for v in violations)
    assert any("redis_password" in v for v in violations)
    assert any("milvus_password" in v for v in violations)


def test_should_pass_when_production_secrets_overridden():
    """Given 生产模式且强密钥/强口令已覆盖, When 配置校验,
    Then 无违规项"""
    settings = Settings(
        app_env="prod",
        jwt_secret_key="x" * 64,
        postgres_password="prod-pg-strong-pass-123456",
        redis_password="prod-redis-strong-pass-123456",
        milvus_password="prod-milvus-strong-pass-123456",
        cors_allow_origins="https://agent.example.com",
    )

    violations = validate_production_settings(settings)

    assert violations == []


def test_should_reject_wildcard_cors_in_production():
    """Given 生产模式 CORS 配置为通配符, When 配置校验,
    Then 返回 CORS 违规项"""
    settings = Settings(
        app_env="prod",
        jwt_secret_key="x" * 64,
        postgres_password="prod-pg-strong-pass-123456",
        redis_password="prod-redis-strong-pass-123456",
        milvus_password="prod-milvus-strong-pass-123456",
        cors_allow_origins="*",
    )

    violations = validate_production_settings(settings)

    assert any("CORS" in v for v in violations)


def test_should_skip_validation_in_dev_mode():
    """Given 开发模式且使用默认凭证, When 配置校验,
    Then 返回空列表(开发环境允许默认值,保持向后兼容)"""
    settings = Settings(app_env="dev")

    violations = validate_production_settings(settings)

    assert violations == []


def test_should_reject_invalid_system_provider():
    settings = Settings(
        app_env="prod",
        jwt_secret_key="x" * 64,
        postgres_password="prod-pg-strong-pass-123456",
        redis_password="prod-redis-strong-pass-123456",
        milvus_password="prod-milvus-strong-pass-123456",
        crm_tool_provider="live",
        cors_allow_origins="https://agent.example.com",
    )

    violations = validate_production_settings(settings)

    assert any("crm_tool_provider" in violation for violation in violations)


def test_should_require_oidc_settings_before_enabling_sso():
    settings = Settings(
        app_env="prod",
        jwt_secret_key="x" * 64,
        postgres_password="prod-pg-strong-pass-123456",
        redis_password="prod-redis-strong-pass-123456",
        milvus_password="prod-milvus-strong-pass-123456",
        sso_enabled=True,
        cors_allow_origins="https://agent.example.com",
    )

    violations = validate_production_settings(settings)

    assert any("SSO_ENABLED=true" in violation for violation in violations)
