# Design

复用 C04 的 `prepare_chat_session` 与 `require_session_access`。PostgreSQL 负责持久化用户与会话的归属。只有取消会话允许管理员例外。普通用户访问其他用户或不存在的会话时收到同一错误。既有会话的续聊更新带所有者条件，首次建单遇 ID 冲突时停止执行。
