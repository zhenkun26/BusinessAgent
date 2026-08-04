-- ============================================
-- Migration 003: 用户密码哈希初始化(认证加固)
-- 适用于已在运行的环境(init.sql 已同步更新,新环境无需执行)
-- 执行: docker compose exec -T postgres psql -U agent enterprise_agent < deploy/migrations/003_user_password_hash.sql
-- 幂等: UPDATE 仅覆盖 password_hash 为空的行
-- 默认密码: ChangeMe123!(生产环境首次登录后必须修改)
-- ============================================

UPDATE users
SET password_hash = '$2b$12$LZNwZxsJxS.i9xKL7spB5eRn.X0p8l5hScV3v5ulwow6.8RFs4hKO'
WHERE password_hash IS NULL OR password_hash = '';

-- 说明: 启用 AUTH_REQUIRE_PASSWORD=true 后,种子用户使用上述默认密码登录。
-- 生产上线前请通过用户管理 API 或 SQL 为每个用户重置独立强密码。
