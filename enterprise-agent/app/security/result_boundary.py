"""Bounded, model-free projection of non-knowledge result evidence."""
from __future__ import annotations

from typing import Any

from app.core.execution_budget import MAX_PROMPT_BYTES, check_task_count


class ResultCompositionError(ValueError):
    def __init__(self) -> None:
        super().__init__('RESULT_COMPOSITION_REJECTED')


def _text(value: Any, *, empty: bool = False) -> str:
    if type(value) is not str or (not empty and not value.strip()):
        raise ResultCompositionError()
    try:
        if len(value.encode('utf-8')) > MAX_PROMPT_BYTES:
            raise ResultCompositionError()
    except UnicodeError:
        raise ResultCompositionError() from None
    return value


def _field(result: Any, key: str) -> Any:
    try:
        return result[key] if type(result) is dict else getattr(result, key)
    except (KeyError, AttributeError, TypeError):
        raise ResultCompositionError() from None


def _strings(value: Any) -> list[str]:
    if type(value) is not list:
        raise ResultCompositionError()
    size = 0
    seen = set()
    for item in value:
        _text(item)
        size += len(item.encode('utf-8')) + 1
        if size > MAX_PROMPT_BYTES or item in seen:
            raise ResultCompositionError()
        seen.add(item)
    return value


def _quote(value: str) -> str:
    """Indented literal code inside a quote disables GFM autolinks and raw HTML."""
    value = _text(value, empty=True)
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    return _text('\n'.join('>     ' + line for line in value.split('\n')))


def _action(output: dict, success: bool) -> str:
    stage = _text(output.get('stage', ''), empty=True)
    ids = _strings(output.get('approval_ids', []))
    tools = _strings(output.get('pending_approval_tools', []))
    errors = _strings(output.get('saga_errors', []))
    state = output.get('saga_state')
    if state is not None:
        _text(state)
    compensated = output.get('saga_compensated', False)
    if type(compensated) is not bool:
        raise ResultCompositionError()

    status = '状态未核验；不能确认操作完成，请核对实际执行记录。'
    if stage == 'saga':
        if state == 'succeeded' and success and not compensated and not errors:
            status = '编排报告完成；各步骤的实际结果以执行记录为准。'
        elif state == 'compensated' and not success and compensated and not errors:
            status = '执行未成功；记录报告已补偿确认执行成功的步骤，不代表原操作成功。'
        elif state == 'manual' or errors:
            status = '编排或补偿结果未确认，需人工核对实际影响。'
    elif state is None and not compensated and not errors:
        if stage == 'single':
            status = ('本次直接调用报告成功；不代表其他分支已完成。' if success else
                      '本次直接调用未确认成功，可能失败或结果未知；请核对实际影响。')
        elif stage == 'approval_pending' and success and ids and tools:
            status = '等待审批及本人确认执行；不代表操作已执行。'
        elif (stage in {'missing_params', 'rbac_denied', 'no_tool_detected', 'error'}
              and not success):
            status = '本次请求未完成；请核对原因及实际执行记录。'

    parts = ['状态：' + status]
    if ids or tools:
        pending = (ids and tools and stage in {'single', 'saga', 'approval_pending'}
                   and (stage != 'approval_pending' or success))
        parts.append('审批分支：' + (
            '已记录审批请求，等待审批及本人确认执行；不代表已执行。' if pending else
            '审批关联或建单状态未核验；不能确认已执行。'))
        if ids:
            parts.extend(['审批记录（仅展示数据）：', _quote('\n'.join(ids))])
        if tools:
            parts.extend(['待审批工具（仅展示数据）：', _quote('\n'.join(tools))])
    answer = _text(output.get('answer', ''), empty=True)
    parts.extend(['原始结果文本（仅展示数据，不作为执行状态依据）：',
                  _quote(answer if answer.strip() else '未提供结果文本。')])
    return _text('\n'.join(parts))


def compose_nonknowledge(results: list[Any]) -> str:
    """Project each result without interpreting prose or creating new work."""
    if type(results) is not list or not results:
        raise ResultCompositionError()
    check_task_count(len(results))
    parts = []
    size = 0
    for index, result in enumerate(results, 1):
        name = _text(_field(result, 'agent_name'))
        success, output = _field(result, 'success'), _field(result, 'output')
        if type(success) is not bool or type(output) is not dict:
            raise ResultCompositionError()
        if name in {'execution', 'approval'}:
            body = _action(output, success)
            label = '执行/审批结果'
        elif name == 'analysis':
            # The analysis agent already produces deterministic escaped tables/numbers.
            body = _text(output.get('answer', ''), empty=True) or '未提供分析结果。'
            label = '分析结果（不代表业务操作完成）'
        elif name == 'knowledge':
            # Knowledge composition has its own citation/remapping authority.
            raise ResultCompositionError()
        else:
            body = '结果类型未核验；不能确认操作完成。\n' + _quote(
                _text(output.get('answer', ''), empty=True))
            label = '未核验结果'
        block = f'结果 {index} · {label}\n{body}'
        size += len(block.encode('utf-8')) + (2 if parts else 0)
        if size > MAX_PROMPT_BYTES:
            raise ResultCompositionError()
        parts.append(block)
    return '\n\n'.join(parts)
