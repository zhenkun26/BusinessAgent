-- ============================================
-- Migration 005: OIDC SSO 身份映射字段（仅数据结构，不启用登录）
-- 执行: docker compose exec -T postgres psql -U agent enterprise_agent < deploy/migrations/005_user_sso_identity.sql
-- 幂等: ADD COLUMN IF NOT EXISTS + IF NOT EXISTS 索引
-- 回滚（确认无 SSO 映射数据后手动执行）:
--   DROP INDEX IF EXISTS idx_users_sso_identity;
--   ALTER TABLE users DROP COLUMN IF EXISTS sso_issuer;
--   ALTER TABLE users DROP COLUMN IF EXISTS sso_subject;
-- ============================================

ALTER TABLE users ADD COLUMN IF NOT EXISTS sso_issuer VARCHAR(512);
ALTER TABLE users ADD COLUMN IF NOT EXISTS sso_subject VARCHAR(255);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_sso_identity
    ON users(sso_issuer, sso_subject)
    WHERE sso_issuer IS NOT NULL AND sso_subject IS NOT NULL;
