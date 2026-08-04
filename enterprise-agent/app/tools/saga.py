"""Saga 补偿事务协调器(对应 v3 方案 6.6 节)

职责:
- 管理多步骤工具调用的补偿事务
- 顺序执行多个 ACTION 类工具
- 任一步骤失败时,反向回滚已成功的步骤
- 保证最终一致性(非 ACID,但可恢复)

适用场景:
- 多步骤业务流程:查客户 → 创建 CRM 任务 → 发邮件通知
- 任一步骤失败需回滚前面已成功的操作

不适用场景:
- 单个工具调用(无需 Saga)
- QUERY 类工具(无副作用,无需补偿)

执行流程:
    步骤1成功 → 步骤2成功 → 步骤3失败
                              ↓
    补偿步骤2 → 补偿步骤1(反向顺序)
                              ↓
    返回 SagaResult(success=False, compensated=True)

设计要点:
- async/await 全程(符合 hard constraint)
- 补偿失败不阻断,记录到 compensation_errors(运维介入)
- 支持跳过补偿(skip_compensation,仅查询类步骤失败时用)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from loguru import logger

from app.observability.tracing import (
    record_span_attributes,
    record_span_event,
    traced_span,
)
from app.tools.base import BaseTool, ToolCategory, ToolResult, get_tool


# ============ 数据契约 ============


class SagaStepStatus(str, Enum):
    """单步骤状态"""

    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"
    SKIPPED = "skipped"  # 跳过(查询类失败不阻断)


@dataclass
class SagaStep:
    """Saga 单步骤定义"""

    step_id: str
    tool_name: str
    params: dict[str, Any]
    # 该步骤失败时是否阻断后续(默认 True;False 表示跳过继续)
    block_on_failure: bool = True
    # 执行结果(运行时填充)
    status: SagaStepStatus = SagaStepStatus.PENDING
    result: Optional[ToolResult] = None
    error: Optional[str] = None
    # 补偿结果(运行时填充)
    compensation_result: Optional[ToolResult] = None


@dataclass
class SagaResult:
    """Saga 协调器最终结果"""

    success: bool
    steps: list[SagaStep]
    total_latency_ms: int
    # 是否触发了补偿
    compensated: bool = False
    # 补偿失败的步骤(需运维介入)
    compensation_errors: list[str] = field(default_factory=list)
    # 聚合输出(各步骤 output 合并)
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


# ============ Saga 协调器 ============


class SagaCoordinator:
    """Saga 补偿事务协调器

    用法:
        saga = SagaCoordinator(context={"user_id": "u001", "role": "manager"})
        saga.add_step("step1", "create_crm_task", {"customer_id": "C001", ...})
        saga.add_step("step2", "send_email_internal", {"to": [...], ...})
        result = await saga.execute()

        if not result.success:
            # Saga 已自动补偿,检查 compensation_errors 是否有需介入的
            ...
    """

    def __init__(self, context: dict[str, Any]):
        """
        Args:
            context: 调用上下文(user_id, role, dept, jwt_token, request_id)
        """
        self.context = context
        self.steps: list[SagaStep] = []

    def add_step(
        self,
        step_id: str,
        tool_name: str,
        params: dict[str, Any],
        block_on_failure: bool = True,
    ) -> "SagaCoordinator":
        """添加一个步骤(链式调用)

        Args:
            step_id: 步骤唯一 ID
            tool_name: 工具名(对应注册表)
            params: 工具入参
            block_on_failure: 失败时是否阻断后续并触发补偿
                             (False 表示跳过继续,如查询类步骤)
        """
        self.steps.append(
            SagaStep(
                step_id=step_id,
                tool_name=tool_name,
                params=params,
                block_on_failure=block_on_failure,
            )
        )
        return self

    async def execute(self) -> SagaResult:
        """执行 Saga 事务

        顺序执行所有步骤,任一 block_on_failure=True 的步骤失败时触发补偿。
        """
        start = time.time()
        completed_steps: list[SagaStep] = []

        # tracing: 整个 Saga 作为一个 span
        with traced_span(
            "saga.execute",
            attributes={
                "saga.steps_count": len(self.steps),
                "saga.user_id": self.context.get("user_id", ""),
                "saga.role": self.context.get("role", ""),
            },
        ):
            logger.info(f"Saga 开始: 共 {len(self.steps)} 步, context_user={self.context.get('user_id')}")

            for step in self.steps:
                step.status = SagaStepStatus.EXECUTING
                logger.info(f"Saga 步骤执行: step_id={step.step_id}, tool={step.tool_name}")

                tool = get_tool(step.tool_name)
                if tool is None:
                    step.status = SagaStepStatus.FAILED
                    step.error = f"工具未注册: {step.tool_name}"
                    logger.error(f"Saga 步骤失败: {step.error}")
                    record_span_event("saga.tool_not_registered", {
                        "step_id": step.step_id,
                        "tool": step.tool_name,
                    })

                    if step.block_on_failure:
                        # 触发补偿
                        await self._compensate(completed_steps)
                        record_span_attributes({
                            "saga.success": False,
                            "saga.compensated": True,
                        })
                        return SagaResult(
                            success=False,
                            steps=self.steps,
                            total_latency_ms=int((time.time() - start) * 1000),
                            compensated=True,
                            error=step.error,
                            outputs=self._aggregate_outputs(completed_steps),
                        )
                    else:
                        step.status = SagaStepStatus.SKIPPED
                        continue

                # 执行工具(span 在 tool.invoke 内自动创建)
                result = await tool.invoke(step.params, self.context)
                step.result = result

                if result.success:
                    step.status = SagaStepStatus.SUCCESS
                    completed_steps.append(step)
                    logger.info(
                        f"Saga 步骤成功: step_id={step.step_id}, "
                        f"latency={result.latency_ms}ms"
                    )
                else:
                    step.status = SagaStepStatus.FAILED
                    step.error = result.error
                    logger.warning(
                        f"Saga 步骤失败: step_id={step.step_id}, error={result.error}"
                    )
                    record_span_event("saga.step_failed", {
                        "step_id": step.step_id,
                        "tool": step.tool_name,
                        "error": result.error or "",
                    })

                    if step.block_on_failure:
                        # 触发补偿
                        compensation_errors = await self._compensate(completed_steps)
                        record_span_attributes({
                            "saga.success": False,
                            "saga.compensated": True,
                            "saga.compensation_errors": len(compensation_errors),
                        })
                        return SagaResult(
                            success=False,
                            steps=self.steps,
                            total_latency_ms=int((time.time() - start) * 1000),
                            compensated=True,
                            compensation_errors=compensation_errors,
                            error=f"步骤 {step.step_id} 失败: {result.error}",
                            outputs=self._aggregate_outputs(completed_steps),
                        )
                    else:
                        step.status = SagaStepStatus.SKIPPED
                        logger.info(f"Saga 步骤跳过(非阻断): step_id={step.step_id}")
                        continue

            # 全部成功
            total_ms = int((time.time() - start) * 1000)
            logger.info(f"Saga 全部成功: {len(completed_steps)}/{len(self.steps)} 步, latency={total_ms}ms")

            record_span_attributes({
                "saga.success": True,
                "saga.completed_steps": len(completed_steps),
                "saga.latency_ms": total_ms,
            })

            return SagaResult(
                success=True,
                steps=self.steps,
                total_latency_ms=total_ms,
                compensated=False,
                outputs=self._aggregate_outputs(completed_steps),
            )

    async def _compensate(self, completed_steps: list[SagaStep]) -> list[str]:
        """反向补偿已成功的步骤

        Args:
            completed_steps: 已成功执行的步骤(按执行顺序)

        Returns:
            补偿失败的错误列表(需运维介入)
        """
        compensation_errors: list[str] = []

        # 反向顺序补偿
        for step in reversed(completed_steps):
            tool = get_tool(step.tool_name)
            if tool is None:
                err = f"补偿失败: 工具 {step.tool_name} 未注册(step_id={step.step_id})"
                compensation_errors.append(err)
                step.status = SagaStepStatus.COMPENSATION_FAILED
                continue

            # QUERY 类工具无副作用,无需补偿
            if tool.category == ToolCategory.QUERY:
                step.status = SagaStepStatus.COMPENSATED
                logger.info(f"Saga 补偿跳过(QUERY 类): step_id={step.step_id}")
                continue

            # 获取补偿数据
            compensation_data = step.result.compensation_data if step.result else {}
            if not compensation_data:
                logger.warning(
                    f"Saga 补偿无数据: step_id={step.step_id}, tool={step.tool_name}"
                )
                step.status = SagaStepStatus.COMPENSATED
                continue

            try:
                logger.info(
                    f"Saga 补偿执行: step_id={step.step_id}, tool={step.tool_name}, "
                    f"action={compensation_data.get('action')}"
                )
                comp_result = await tool.compensate(compensation_data)
                step.compensation_result = comp_result

                if comp_result.success:
                    step.status = SagaStepStatus.COMPENSATED
                    logger.info(f"Saga 补偿成功: step_id={step.step_id}")
                else:
                    step.status = SagaStepStatus.COMPENSATION_FAILED
                    err = (
                        f"补偿失败: step_id={step.step_id}, tool={step.tool_name}, "
                        f"error={comp_result.error}"
                    )
                    compensation_errors.append(err)
                    logger.error(err)

            except Exception as e:  # noqa: BLE001
                step.status = SagaStepStatus.COMPENSATION_FAILED
                err = f"补偿异常: step_id={step.step_id}, error={type(e).__name__}: {e}"
                compensation_errors.append(err)
                logger.exception(err)

        if compensation_errors:
            logger.error(
                f"Saga 补偿完成,有 {len(compensation_errors)} 个补偿失败(需运维介入)"
            )
        else:
            logger.info(f"Saga 补偿完成: {len(completed_steps)} 个步骤全部补偿成功")

        return compensation_errors

    @staticmethod
    def _aggregate_outputs(completed_steps: list[SagaStep]) -> dict[str, Any]:
        """聚合各步骤输出"""
        outputs: dict[str, Any] = {}
        for step in completed_steps:
            if step.result and step.result.output:
                outputs[step.step_id] = step.result.output
        return outputs
