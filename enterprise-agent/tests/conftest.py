"""pytest 公共测试基座

约定(对应 quality-testing 规格):
- 全部测试离线可运行:Mock 数据库/网络/LLM/文件系统,不依赖 Docker 与外部服务
- 测试命名:test_should_<expected_behaviour>_when_<condition>
- 结构:Given-When-Then(Arrange-Act-Assert)

提供:
- FakeRow / FakeResult / FakeSession:内存版数据库会话,记录 SQL 并返回预置行
- fake_session_factory:生成可注入的会话工厂(替换 app.core.database 依赖)
"""

from __future__ import annotations

from typing import Any, Optional

import pytest


class FakeRow:
    """模拟一行数据库结果,属性即列名"""

    def __init__(self, **kwargs: Any) -> None:
        for column_name, value in kwargs.items():
            setattr(self, column_name, value)


class FakeResult:
    """模拟 execute() 返回值"""

    def __init__(self, rows: Optional[list[FakeRow]] = None) -> None:
        self._rows = rows or []

    def fetchall(self) -> list[FakeRow]:
        return self._rows

    def fetchone(self) -> Optional[FakeRow]:
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self) -> Optional[FakeRow]:
        """兼容 SQLAlchemy 的 scalar_one_or_none 语义"""
        return self._rows[0] if len(self._rows) == 1 else None

    def scalar(self) -> Any:
        if not self._rows:
            return 0
        row_values = list(vars(self._rows[0]).values())
        return row_values[0] if row_values else 0


class FakeSession:
    """内存版 AsyncSession:记录已执行 SQL 供断言,按队列返回预置结果"""

    def __init__(self, responses: Optional[list[FakeResult]] = None) -> None:
        self.executed_sql: list[str] = []
        self.executed_params: list[dict] = []
        self._responses = list(responses or [])
        self.commits: int = 0

    async def execute(self, sql: str, params: Optional[dict] = None) -> FakeResult:
        self.executed_sql.append(str(sql))
        self.executed_params.append(params or {})
        if self._responses:
            return self._responses.pop(0)
        return FakeResult()

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def fake_session_factory():
    """返回一个工厂:传入 FakeSession,得到可 async with 的会话工厂"""

    def make_factory(session: FakeSession):
        class _FakeFactory:
            def __call__(self) -> "_FakeFactory":
                return self

            async def __aenter__(self) -> FakeSession:
                return session

            async def __aexit__(self, *exc_info: Any) -> None:
                return None

        return _FakeFactory()

    return make_factory
