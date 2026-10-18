"""Durable Saga coordination; restart recovery never resumes fresh forward work."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import time
from typing import Any, Optional
import uuid

from app.tools.base import ToolCategory, ToolResult, get_tool
from app.security.redaction import redact_value


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
    operation_id: Optional[str] = None
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
    saga_id: Optional[str] = None
    state: Optional[str] = None


class SagaCoordinator:
    def __init__(self, context: dict[str, Any]):
        self.context = context
        self.steps: list[SagaStep] = []

    def add_step(self, step_id: str, tool_name: str, params: dict[str, Any],
                 block_on_failure: bool = True, operation_id: Optional[str] = None) -> "SagaCoordinator":
        self.steps.append(SagaStep(step_id, tool_name, params, block_on_failure, operation_id))
        return self

    async def execute(self) -> SagaResult:
        from app.core.saga_store import SagaStore
        from app.core.saga_retry import guarded, recover_owned
        from app.core.tool_operations import OperationError, saga_dispatch
        started = time.monotonic()
        sid = None
        try:
            definitions = []
            for step in self.steps:
                tool = get_tool(step.tool_name)
                if tool is None:
                    raise OperationError('SAGA_TOOL_UNKNOWN')
                definitions.append({'step_id': step.step_id, 'tool': step.tool_name,
                    'params': step.params, 'operation_id': step.operation_id,
                    'action': tool.category == ToolCategory.ACTION,
                    'block_on_failure': step.block_on_failure})
            if not any(item['action'] for item in definitions):
                # Queries have no recoverable business effects and need no operation IDs.
                for step in self.steps:
                    step.result = await get_tool(step.tool_name).invoke(step.params, self.context)
                    step.status = SagaStepStatus.SUCCESS if step.result.success else SagaStepStatus.SKIPPED
                    if not step.result.success and step.block_on_failure:
                        return SagaResult(False, self.steps, 0, error='SAGA_QUERY_FAILED')
                return SagaResult(True, self.steps, 0, outputs=self._aggregate_outputs(self.steps))
            store = SagaStore()
            owner = str(uuid.uuid4())
            run, created = await store.prepare(definitions, self.context, owner)
            sid = str(run['saga_id'])

            async def forward() -> str:
                with saga_dispatch(sid, owner):
                    for slot, step in enumerate(self.steps):
                        await store.renew(sid, owner)
                        result = await get_tool(step.tool_name).invoke(
                            step.params, {**self.context, 'operation_id': step.operation_id,
                                          'step_id': step.step_id})
                        # Persist only the same sanitized result exposed at the tool boundary.
                        await store.record(sid, owner, slot, redact_value(asdict(result)))
                        if not result.success and (definitions[slot]['action'] or step.block_on_failure):
                            return await recover_owned(store, sid, owner)
                    await store.finish(sid, owner, 'succeeded')
                    return 'succeeded'

            if created:
                await guarded(store, sid, owner, forward)
                run = await store.load(sid)
            for step, recorded in zip(self.steps, run['steps'], strict=True):
                if recorded['result'] is not None:
                    step.result = ToolResult(**recorded['result'])
                    step.status = SagaStepStatus.SUCCESS if step.result.success else SagaStepStatus.FAILED
                if recorded['compensation_state'] == 'committed':
                    effect = (recorded['compensation_receipt'] or {}).get('operation', {}).get('effect')
                    step.status = (SagaStepStatus.COMPENSATION_FAILED if effect == 'recall_requested'
                                   else SagaStepStatus.COMPENSATED)
            state = run['state']
            return SagaResult(state == 'succeeded', self.steps,
                int((time.monotonic() - started) * 1000), compensated=state == 'compensated',
                compensation_errors=[] if state in {'succeeded', 'compensated'} else ['SAGA_UNRESOLVED'],
                outputs=self._aggregate_outputs(self.steps),
                error=None if state == 'succeeded' else 'SAGA_' + state.upper(), saga_id=sid, state=state)
        except Exception:
            # Retained recovery job survives cancellation/crash/store ambiguity. Never leak exceptions.
            return SagaResult(False, self.steps, int((time.monotonic() - started) * 1000),
                              error='SAGA_RECOVERY_REQUIRED', saga_id=sid, state='unknown')

    @staticmethod
    def _aggregate_outputs(steps: list[SagaStep]) -> dict[str, Any]:
        return {step.step_id: step.result.output for step in steps
                if step.result and step.result.success and step.result.output}
