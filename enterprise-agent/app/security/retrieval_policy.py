"""Shared, fail-closed authorization for every knowledge retrieval backend."""

from dataclasses import dataclass
import json
import re
from typing import Any


class RetrievalAccessError(ValueError):
    """Invalid identity/filter context; never retry with a broader filter."""


def checked_string(value: Any, max_bytes: int) -> str:
    if not isinstance(value, str) or not value:
        raise RetrievalAccessError('RETRIEVAL_FILTER_INVALID')
    try:
        size = len(value.encode('utf-8'))
    except UnicodeError:
        raise RetrievalAccessError('RETRIEVAL_FILTER_INVALID') from None
    if size > max_bytes or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
        raise RetrievalAccessError('RETRIEVAL_FILTER_INVALID')
    return value


def milvus_literal(value: str, max_bytes: int = 8192) -> str:
    """Encode one double-quoted literal; identifiers/operators are never caller input."""
    return json.dumps(checked_string(value, max_bytes), ensure_ascii=False)


def valid_namespace(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', value) is not None


@dataclass(frozen=True)
class RetrievalScope:
    role: str
    namespaces: tuple[str, ...] | None  # None is the explicit administrator wildcard.
    doc_types: tuple[str, ...] | None

    def allows(self, namespace: Any, roles: Any, active: Any, doc_type: Any) -> bool:
        try:
            checked_string(doc_type, 32)
        except RetrievalAccessError:
            return False
        return (active is True and valid_namespace(namespace)
                and (self.namespaces is None or namespace in self.namespaces)
                and isinstance(roles, list) and all(isinstance(role, str) for role in roles)
                and self.role in roles and isinstance(doc_type, str) and bool(doc_type)
                and (self.doc_types is None or doc_type in self.doc_types))

    def allows_result(self, result: Any) -> bool:
        return self.allows(getattr(result, 'dept_namespace', None),
                           getattr(result, 'access_roles', None),
                           getattr(result, 'is_active', None), getattr(result, 'doc_type', None))

    def milvus_expression(self) -> str:
        parts = ['is_active == true', f'ARRAY_CONTAINS(access_roles, {milvus_literal(self.role)})']
        if self.namespaces is not None:
            values = ', '.join(milvus_literal(value) for value in self.namespaces)
            parts.append(f'dept_namespace in [{values}]')
        if self.doc_types is not None:
            if not self.doc_types:
                parts.append('is_active == false')  # Explicit empty allowlist, valid predicate.
            else:
                values = ', '.join(milvus_literal(value) for value in self.doc_types)
                parts.append(f'doc_type in [{values}]')
        return ' and '.join(parts)


def resolve_scope(
    user_role: str | None, department: str | None, doc_types: list[str] | None = None,
    *, active_only: bool = True,
) -> RetrievalScope:
    from app.security.rbac import ROLE_NAMESPACES

    if (not isinstance(user_role, str) or user_role not in ROLE_NAMESPACES
            or active_only is not True):
        raise RetrievalAccessError('RETRIEVAL_ACCESS_DENIED')
    grants = ROLE_NAMESPACES[user_role]
    if department not in (None, ''):
        if not valid_namespace(department) or ('*' not in grants and department not in grants):
            raise RetrievalAccessError('RETRIEVAL_ACCESS_DENIED')
    if '*' in grants:
        namespaces = None
    elif user_role == 'manager':
        namespaces = tuple(grants)
    else:
        namespaces = tuple(dict.fromkeys([department, 'shared_company'])) if department else (
            'shared_company',)
    if doc_types is not None:
        if not isinstance(doc_types, list) or len(doc_types) > 32:
            raise RetrievalAccessError('RETRIEVAL_FILTER_INVALID')
        types = tuple(dict.fromkeys(checked_string(value, 32) for value in doc_types))
    else:
        types = None
    return RetrievalScope(user_role, namespaces, types)
