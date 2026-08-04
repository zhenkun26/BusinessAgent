-- ============================================
-- Migration 002: documents 台账增强(知识库运营闭环)
-- 适用于已在运行的环境(init.sql 已同步更新,新环境无需执行)
-- 执行: docker compose exec -T postgres psql -U agent enterprise_agent < deploy/migrations/002_documents_ledger.sql
-- 幂等:所有 DDL 均带 IF NOT EXISTS,可重复执行
-- ============================================

-- 审核字段(管理员审核知识候选时记录)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(64) REFERENCES users(user_id);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS reject_reason TEXT;

-- 入库失败标记(向量写入失败时保留,供 worker 重试)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS ingest_error TEXT;

-- 文档正文(反馈候选仅存标题,审核通过入库时需要正文作为检索片段)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content TEXT;

-- 来源会话(反馈候选追溯:该候选由哪次会话的反馈生成)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS source_session_id VARCHAR(64);

-- 检索降级链第三级:PostgreSQL tsvector 全文检索
-- simple 配置先提供可控关键词匹配,后续可换中文分词
ALTER TABLE documents ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE INDEX IF NOT EXISTS idx_documents_search
    ON documents USING GIN (search_vector);

-- 审核队列索引(draft 候选 + active/rejected 台账)
CREATE INDEX IF NOT EXISTS idx_documents_review_status
    ON documents (status) WHERE status IN ('draft', 'active', 'rejected');

-- 台账唯一性:document_id 已是主键;为 content_hash 建立查找索引(去重判断用)
CREATE INDEX IF NOT EXISTS idx_documents_content_hash
    ON documents (content_hash);
