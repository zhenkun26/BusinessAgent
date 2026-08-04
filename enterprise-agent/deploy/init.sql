-- ============================================
-- Hello，小A——企业知识工作流 Agent - 数据库初始化
-- ============================================

-- 用户与权限
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE NOT NULL,
    username VARCHAR(128) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(32) NOT NULL,  -- salesperson / customer_service / finance / manager / admin
    department VARCHAR(64),
    password_hash VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- 会话记录
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    original_query TEXT,
    status VARCHAR(32) DEFAULT 'pending',  -- pending / running / completed / failed
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    token_count INTEGER DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

-- 审批请求(P1-1 支持批量)
CREATE TABLE IF NOT EXISTS approval_requests (
    approval_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id),
    requester_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    batch_id VARCHAR(64),
    operation_type VARCHAR(64) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    summary TEXT,
    prefill_payload JSONB,
    approver_roles JSONB NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',  -- pending / approved / rejected / timeout / approved_pending_reauth / executed
    approver_id VARCHAR(64) REFERENCES users(user_id),
    comment TEXT,
    requester_token TEXT,  -- 加密存储, 审批恢复时使用
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    decided_at TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_approvals_session_id ON approval_requests(session_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approvals_approver ON approval_requests(approver_id);

-- 审计日志(P1-10 含容错设计)
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    session_id VARCHAR(64),
    user_id VARCHAR(64),
    tool_name VARCHAR(64),
    input_summary TEXT,
    output_summary TEXT,
    success BOOLEAN,
    latency_ms INTEGER,
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);

-- 长期记忆(跨会话)
CREATE TABLE IF NOT EXISTS user_memories (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    memory JSONB NOT NULL,
    memory_type VARCHAR(32),  -- preference / fact / context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memories_user_id ON user_memories(user_id);
CREATE INDEX IF NOT EXISTS idx_memories_last_accessed ON user_memories(last_accessed_at);

-- Saga 事务记录(P0-4)
CREATE TABLE IF NOT EXISTS saga_transactions (
    saga_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id),
    batch_id VARCHAR(64),
    status VARCHAR(32) DEFAULT 'running',  -- running / completed / compensated / failed
    actions JSONB NOT NULL,  -- 计划执行的动作
    executed_actions JSONB,  -- 已执行的动作
    compensation_results JSONB,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_saga_session ON saga_transactions(session_id);
CREATE INDEX IF NOT EXISTS idx_saga_status ON saga_transactions(status);

-- 用户反馈(P1-5 反馈学习闭环预留)
CREATE TABLE IF NOT EXISTS user_feedback (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL REFERENCES sessions(session_id),
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    message_id VARCHAR(64),
    feedback_type VARCHAR(16) NOT NULL,  -- like / dislike
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_session ON user_feedback(session_id);

-- 文档元数据(知识库运营后台预留 P1-4)
CREATE TABLE IF NOT EXISTS documents (
    document_id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    source_url VARCHAR(1024),
    doc_type VARCHAR(32),  -- policy / product / faq / manual
    dept_namespace VARCHAR(64),
    status VARCHAR(32) DEFAULT 'draft',  -- draft / active / archived / deleted
    access_roles JSONB,
    content_hash VARCHAR(64),
    uploaded_by VARCHAR(64) REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_namespace ON documents(dept_namespace);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- Prompt 版本管理(P2-1:A/B 测试与回滚)
-- 模板语法为 Python str.format,JSON 示例花括号需 {{ }} 转义(与代码内约定一致)
CREATE TABLE IF NOT EXISTS prompt_versions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,          -- prompt 逻辑名,如 planner_intent_classify
    version INTEGER NOT NULL,           -- 从 1 递增
    content TEXT NOT NULL,              -- 模板原文(含 {{ }} 转义)
    status VARCHAR(16) DEFAULT 'draft', -- draft / active / archived
    traffic_weight INTEGER DEFAULT 0,   -- A/B 分流权重 0-100(仅 active 版本有效)
    created_by VARCHAR(64) REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activated_at TIMESTAMP,
    UNIQUE (name, version)
);

CREATE INDEX IF NOT EXISTS idx_prompt_versions_name ON prompt_versions(name);
CREATE INDEX IF NOT EXISTS idx_prompt_versions_status ON prompt_versions(status);

-- ============================================
-- 种子数据(开发环境,贴近真实企业场景)
-- 设计原则:覆盖 5 角色 × 4 部门,支持跨部门协作/Saga/批量审批/RBAC 测试
-- ============================================

-- ---- 用户(12 人,覆盖全部角色与部门) ----
INSERT INTO users (user_id, username, email, role, department) VALUES
    -- 销售部(4 人:3 销售员 + 1 经理)
    ('user_sales_001', '销售员张三', 'zhangsan@example.com', 'salesperson', 'dept_sales'),
    ('user_sales_002', '销售员王芳', 'wangfang@example.com', 'salesperson', 'dept_sales'),
    ('user_sales_003', '销售员李雷', 'lilei@example.com', 'salesperson', 'dept_sales'),
    ('user_mgr_001',   '销售经理赵六', 'zhaoliu@example.com', 'manager', 'dept_sales'),
    -- 客服部(2 人)
    ('user_cs_001', '客服李四', 'lisi@example.com', 'customer_service', 'dept_cs'),
    ('user_cs_002', '客服韩梅梅', 'hanmeimei@example.com', 'customer_service', 'dept_cs'),
    -- 财务部(2 人:1 专员 + 1 经理)
    ('user_fin_001', '财务王五', 'wangwu@example.com', 'finance', 'dept_finance'),
    ('user_fin_002', '财务经理钱八', 'qianba@example.com', 'manager', 'dept_finance'),
    -- HR 部(1 人,用 customer_service 角色占位)
    ('user_hr_001', 'HR孙九', 'sunjiu@example.com', 'customer_service', 'dept_hr'),
    -- 管理员(1 人)
    ('user_admin_001', '管理员钱七', 'qianqi@example.com', 'admin', 'shared_company')
ON CONFLICT (user_id) DO NOTHING;

-- ---- 知识库文档元数据(与 sample_docs 对齐) ----
INSERT INTO documents (document_id, title, source_url, doc_type, dept_namespace, status, access_roles, uploaded_by) VALUES
    ('doc_policy_sales',    '销售政策',       '/docs/sales_policy.md',     'policy', 'shared_company', 'active', '["salesperson","customer_service","finance","manager","admin"]', 'user_admin_001'),
    ('doc_policy_finance',  '财务报销制度',   '/docs/finance_policy.md',   'policy', 'shared_company', 'active', '["salesperson","customer_service","finance","manager","admin"]', 'user_admin_001'),
    ('doc_manual_product',  '产品手册',       '/docs/product_manual.md',   'manual', 'shared_company', 'active', '["salesperson","customer_service","finance","manager","admin"]', 'user_admin_001'),
    ('doc_faq',             '常见问题FAQ',    '/docs/faq.md',              'faq',    'shared_company', 'active', '["salesperson","customer_service","finance","manager","admin"]', 'user_admin_001'),
    ('doc_policy_aftersale','售后服务政策',   '/docs/aftersale_policy.md', 'policy', 'shared_company', 'active', '["salesperson","customer_service","finance","manager","admin"]', 'user_admin_001'),
    -- 部门私有文档(测试命名空间隔离)
    ('doc_sales_internal',  '销售部内部报价指南', '/docs/sales_internal.md', 'policy', 'dept_sales', 'active', '["salesperson","manager","admin"]', 'user_mgr_001'),
    ('doc_finance_internal','财务部对账流程',     '/docs/finance_internal.md','policy', 'dept_finance', 'active', '["finance","manager","admin"]', 'user_fin_002')
ON CONFLICT (document_id) DO NOTHING;

-- ---- 历史会话(让审批列表/审计日志有历史感) ----
INSERT INTO sessions (session_id, user_id, original_query, status, started_at, completed_at, token_count) VALUES
    ('sess_hist_001', 'user_sales_001', '查询客户 C001 的历史订单', 'completed', CURRENT_TIMESTAMP - interval '2 days', CURRENT_TIMESTAMP - interval '2 days' + interval '15 seconds', 320),
    ('sess_hist_002', 'user_sales_001', '给经理发邮件说明折扣审批流程', 'completed', CURRENT_TIMESTAMP - interval '1 days', CURRENT_TIMESTAMP - interval '1 days' + interval '22 seconds', 580),
    ('sess_hist_003', 'user_cs_001',    '客户 C003 投诉产品bug,创建工单', 'completed', CURRENT_TIMESTAMP - interval '1 days', CURRENT_TIMESTAMP - interval '1 days' + interval '18 seconds', 410),
    ('sess_hist_004', 'user_fin_001',   '查询订单 ORD-2026-003 的回款状态', 'completed', CURRENT_TIMESTAMP - interval '12 hours', CURRENT_TIMESTAMP - interval '12 hours' + interval '8 seconds', 150),
    ('sess_hist_005', 'user_sales_002', '查一下客户 C005 的累计采购额', 'completed', CURRENT_TIMESTAMP - interval '6 hours',  CURRENT_TIMESTAMP - interval '6 hours' + interval '12 seconds', 280),
    ('sess_hist_006', 'user_sales_001', '帮我给 C001 创建跟进任务并发邮件给经理', 'completed', CURRENT_TIMESTAMP - interval '3 hours', CURRENT_TIMESTAMP - interval '3 hours' + interval '25 seconds', 720)
ON CONFLICT (session_id) DO NOTHING;

-- ---- 审批请求(含批量审批场景:batch_id 关联多条) ----
INSERT INTO approval_requests (approval_id, session_id, requester_id, batch_id, operation_type, risk_level, summary, prefill_payload, approver_roles, status, approver_id, comment, created_at, decided_at, expires_at) VALUES
    -- 已审批的历史记录
    ('appr_hist_001', 'sess_hist_002', 'user_sales_001', NULL, 'send_email_external', 'high',
     '向经理赵六发送折扣审批流程说明邮件',
     '{"to":["zhaoliu@example.com"],"subject":"折扣审批流程说明"}'::jsonb,
     '["manager","admin"]'::jsonb, 'approved', 'user_mgr_001', '同意,流程说明准确',
     CURRENT_TIMESTAMP - interval '1 days', CURRENT_TIMESTAMP - interval '1 days' + interval '5 minutes',
     CURRENT_TIMESTAMP + interval '7 days'),
    -- 批量审批场景:同一 batch_id 下 3 条待审批
    -- 注意:prefill_payload 需与动态建单一致的 {"tool_calls":[...]} 格式;
    -- requester_token 无法静态预置(签名密钥在 .env),建库后需运行
    -- scripts/fix_seed_approvals.py 补 token,否则批准后为 approved_pending_reauth
    ('appr_batch_001', 'sess_hist_006', 'user_sales_001', 'batch_2026_001', 'create_crm_task', 'medium',
     '为客户 C001 创建季度跟进任务',
     '{"tool_calls":[{"tool":"create_crm_task","params":{"customer_id":"C001","title":"Q3季度跟进","description":"客户 C001 季度跟进回访","priority":1},"reason":"为客户 C001 创建季度跟进任务"}]}'::jsonb,
     '["manager","admin"]'::jsonb, 'pending', NULL, NULL,
     CURRENT_TIMESTAMP - interval '30 minutes', NULL,
     CURRENT_TIMESTAMP + interval '24 hours'),
    ('appr_batch_002', 'sess_hist_006', 'user_sales_001', 'batch_2026_001', 'send_email_internal', 'medium',
     '通知经理赵六关于 C001 的跟进安排',
     '{"tool_calls":[{"tool":"send_email_internal","params":{"to":["zhaoliu@company.internal"],"subject":"C001跟进安排","body":"关于客户 C001 的季度跟进安排,请知悉。"},"reason":"通知经理赵六关于 C001 的跟进安排"}]}'::jsonb,
     '["manager","admin"]'::jsonb, 'pending', NULL, NULL,
     CURRENT_TIMESTAMP - interval '30 minutes', NULL,
     CURRENT_TIMESTAMP + interval '24 hours'),
    -- appr_batch_003 的 create_ticket 按 RBAC 仅 customer_service/manager 可用,发起人为客服李四
    ('appr_batch_003', 'sess_hist_006', 'user_cs_001', 'batch_2026_001', 'create_ticket', 'medium',
     '为 C001 创建售后协调工单',
     '{"tool_calls":[{"tool":"create_ticket","params":{"title":"C001售后协调","description":"客户 C001 售后协调工单","customer_id":"C001","priority":"high"},"reason":"为 C001 创建售后协调工单"}]}'::jsonb,
     '["manager","admin"]'::jsonb, 'pending', NULL, NULL,
     CURRENT_TIMESTAMP - interval '30 minutes', NULL,
     CURRENT_TIMESTAMP + interval '24 hours')
ON CONFLICT (approval_id) DO NOTHING;

-- ---- 审计日志(历史记录,让审计页面有数据) ----
INSERT INTO audit_logs (event_type, session_id, user_id, tool_name, input_summary, output_summary, success, latency_ms, payload, created_at) VALUES
    ('rag_retrieve',    'sess_hist_001', 'user_sales_001', NULL, '查询 C001 历史订单', '召回 5 条, top_score=0.78', true, 156, '{"stage":"rerank","scene":"OPERATIONAL"}'::jsonb, CURRENT_TIMESTAMP - interval '2 days'),
    ('tool_call',       'sess_hist_002', 'user_sales_001', 'send_email_external', '发邮件给经理', 'message_id=EXT-XXXX', true, 230, '{"recipients":1}'::jsonb, CURRENT_TIMESTAMP - interval '1 days'),
    ('tool_call',       'sess_hist_003', 'user_cs_001',    'create_ticket', '创建bug工单', 'ticket_id=TK-XXXX', true, 180, '{"priority":"high"}'::jsonb, CURRENT_TIMESTAMP - interval '1 days'),
    ('saga_execute',    'sess_hist_006', 'user_sales_001', NULL, '多步骤:C001跟进任务+邮件', '3步全部成功', true, 1850, '{"steps":3,"compensated":false}'::jsonb, CURRENT_TIMESTAMP - interval '3 hours'),
    ('rbac_denied',     NULL,            'user_sales_001', 'send_email_external', '销售员尝试发外部邮件', '权限拒绝', false, 5, '{"required_role":"manager"}'::jsonb, CURRENT_TIMESTAMP - interval '5 hours'),
    ('prompt_injection_blocked', NULL,   'user_sales_002', NULL, '检测到注入:ignore previous instructions', '拦截', false, 3, '{"pattern":"system_override"}'::jsonb, CURRENT_TIMESTAMP - interval '8 hours')
ON CONFLICT DO NOTHING;

-- ---- 用户长期记忆(跨会话偏好) ----
INSERT INTO user_memories (user_id, memory, memory_type, created_at, last_accessed_at) VALUES
    ('user_sales_001', '{"prefers_concise_answer": true, "often_queries": ["折扣政策", "客户跟进"], "language": "zh-CN"}'::jsonb, 'preference', CURRENT_TIMESTAMP - interval '10 days', CURRENT_TIMESTAMP - interval '3 hours'),
    ('user_cs_001',    '{"prefers_concise_answer": false, "often_queries": ["工单流程", "售后政策"], "language": "zh-CN"}'::jsonb, 'preference', CURRENT_TIMESTAMP - interval '8 days', CURRENT_TIMESTAMP - interval '1 days'),
    ('user_fin_001',   '{"prefers_concise_answer": true, "often_queries": ["报销流程", "转账限额"], "language": "zh-CN"}'::jsonb, 'preference', CURRENT_TIMESTAMP - interval '15 days', CURRENT_TIMESTAMP - interval '12 hours')
ON CONFLICT DO NOTHING;

-- ---- Saga 事务历史(含成功与补偿案例) ----
INSERT INTO saga_transactions (saga_id, session_id, batch_id, status, actions, executed_actions, compensation_results, error, created_at, completed_at) VALUES
    ('saga_hist_001', 'sess_hist_006', 'batch_2026_001', 'completed',
     '[{"tool":"query_customer"},{"tool":"create_crm_task"},{"tool":"send_email_internal"}]'::jsonb,
     '[{"tool":"query_customer","success":true},{"tool":"create_crm_task","success":true},{"tool":"send_email_internal","success":true}]'::jsonb,
     NULL, NULL,
     CURRENT_TIMESTAMP - interval '3 hours', CURRENT_TIMESTAMP - interval '3 hours' + interval '2 seconds'),
    ('saga_hist_002', 'sess_hist_003', NULL, 'compensated',
     '[{"tool":"query_customer"},{"tool":"create_ticket"},{"tool":"send_email_external"}]'::jsonb,
     '[{"tool":"query_customer","success":true},{"tool":"create_ticket","success":true},{"tool":"send_email_external","success":false}]'::jsonb,
     '{"compensated_steps":["create_ticket"],"reason":"外部邮件发送失败"}'::jsonb,
     'send_email_external: SMTP 连接超时',
     CURRENT_TIMESTAMP - interval '1 days', CURRENT_TIMESTAMP - interval '1 days' + interval '5 seconds')
ON CONFLICT (saga_id) DO NOTHING;

-- ---- 用户反馈(点赞/点踩历史) ----
INSERT INTO user_feedback (session_id, user_id, message_id, feedback_type, comment, created_at) VALUES
    ('sess_hist_001', 'user_sales_001', 'msg_001', 'like', NULL, CURRENT_TIMESTAMP - interval '2 days'),
    ('sess_hist_003', 'user_cs_001',    'msg_003', 'dislike', '答案缺少工单优先级建议', CURRENT_TIMESTAMP - interval '1 days'),
    ('sess_hist_005', 'user_sales_002', 'msg_005', 'like', NULL, CURRENT_TIMESTAMP - interval '6 hours')
ON CONFLICT DO NOTHING;
