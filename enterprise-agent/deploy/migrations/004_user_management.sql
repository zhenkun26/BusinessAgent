-- ============================================
-- Migration 004: 用户生命周期加固(用户管理 API 前置)
-- 执行: docker compose exec -T postgres psql -U agent enterprise_agent < deploy/migrations/004_user_management.sql
-- 幂等:所有 DDL 均带 IF NOT EXISTS / 条件约束
-- ============================================

-- 1) 回填空密码哈希(默认密码 ChangeMe123!,与 003 一致;生产上线前必须重置)
UPDATE users
SET password_hash = '$2b$12$LZNwZxsJxS.i9xKL7spB5eRn.X0p8l5hScV3v5ulwow6.8RFs4hKO'
WHERE password_hash IS NULL OR password_hash = '';

-- 2) password_hash 必填(认证加固;先回填再收紧)
ALTER TABLE users ALTER COLUMN password_hash SET NOT NULL;

-- 3) is_active 索引(禁用用户即时校验 + 登录过滤)
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- 4) username 唯一(用户管理 API 409 语义;种子数据已唯一)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username);
