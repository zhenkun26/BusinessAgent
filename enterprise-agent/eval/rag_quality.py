"""C17 metric contract v2. Standard library only; no app imports or side effects."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
import re
from typing import Any

REFUSAL_MARKERS = ('未在知识库中找到', '知识库未覆盖', '未覆盖该情形', '未收录',
                   '没有相关信息', '无相关信息', '无法回答', '无法基于', '不足以回答', '没有找到')
CLARIFY_MARKERS = ('请补充', '请明确', '请提供更多信息', '请说明', '澄清', '指的是哪', '能否具体')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_keyword_coverage(text: str, keywords: list[str]) -> tuple[float, list[str], list[str]]:
    """Keep the original case-insensitive substring rule; never widen annotations."""
    hit = [word for word in keywords if word.lower() in text.lower()]
    missed = [word for word in keywords if word.lower() not in text.lower()]
    return len(hit) / len(keywords) if keywords else 0.0, hit, missed


def detect_expected_behavior(answer: str, behavior: str) -> bool:
    markers = {'refuse': REFUSAL_MARKERS, 'clarify': CLARIFY_MARKERS}.get(behavior, ())
    return any(marker in answer for marker in markers)


def load_corpus(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Verify every input byte before reading annotations; no network or mutation."""
    manifest = json.loads((root / 'rag_quality_manifest.json').read_text())
    if manifest['version'] != 'c17-corpus-v1':
        raise ValueError('EVAL_MANIFEST_VERSION')
    entries = [manifest['primary'], manifest['supplemental'], *manifest['documents']]
    for entry in entries:
        path = root / entry['path']
        if (path.is_symlink() or not path.resolve().is_relative_to(root.resolve())
                or digest(path.read_bytes()) != entry['sha256']):
            raise ValueError('EVAL_SOURCE_CHANGED')
    documents = {doc['title']: doc for doc in manifest['documents']}
    cases = []
    for suite in ('primary', 'supplemental'):
        entry = manifest[suite]
        rows = json.loads((root / entry['path']).read_text())['samples']
        if len(rows) != entry['count']:
            raise ValueError('EVAL_CASE_COUNT')
        for row in rows:
            case = {**row, 'suite': suite, 'dataset_sha256': entry['sha256'],
                    'expected_behavior': row.get('expected_behavior', 'answer'),
                    'user_role': row.get('user_role', 'admin'),
                    'user_dept': row.get('user_dept', 'shared_company')}
            doc = documents.get(case['ground_truth_doc'])
            if (case['expected_behavior'] == 'answer'
                    and (doc is None or not case['expected_keywords'])):
                raise ValueError('EVAL_ANNOTATION_INVALID')
            case['expected_document_id'] = doc['document_id'] if doc else ''
            case['source'] = doc
            cases.append(case)
    ids = [case['query_id'] for case in cases]
    if len(set(ids)) != len(ids):
        raise ValueError('EVAL_DUPLICATE_CASE')
    return manifest, cases


@dataclass
class Observation:
    query_id: str
    retrieval_status: str = 'not_run'
    answer_status: str = 'skipped'
    stage: str = 'not_run'
    chunks: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ''
    sources: list[dict[str, Any]] = field(default_factory=list)
    error_code: str = ''
    latency_ms: int = 0
    decision: dict[str, Any] = field(default_factory=dict)


def score_sample(case: dict[str, Any], obs: Observation) -> dict[str, Any]:
    if obs.query_id != case['query_id']:
        raise ValueError('EVAL_ID_MISMATCH')
    retrieval_states = {'ok', 'empty', 'failed', 'not_run'}
    if obs.retrieval_status not in retrieval_states or obs.answer_status not in {
            'ok', 'empty', 'failed', 'skipped', 'blocked'}:
        raise ValueError('EVAL_STATUS_INVALID')
    valid = obs.retrieval_status in {'ok', 'empty'} and obs.answer_status == 'ok'
    normal = case['expected_behavior'] == 'answer'
    chunks = obs.chunks if obs.retrieval_status == 'ok' else []
    rank = next((i for i, chunk in enumerate(chunks[:5], 1)
                 if chunk.get('document_id') == case['expected_document_id']
                 and chunk.get('title') == case['ground_truth_doc']), 0) if normal else 0
    retrieved, _, _ = compute_keyword_coverage(
        '\n'.join(chunk.get('content', '') for chunk in chunks[:5]), case['expected_keywords'])
    coverage, hit, missed = compute_keyword_coverage(
        obs.answer if valid else '', case['expected_keywords'])
    references = re.findall(r'\[来源([^\]]*)\]', obs.answer)
    citations = [int(index) for index in references
                 if index.isascii() and index.isdigit() and len(index) <= 6]
    source_ids = {(s.get('document_id'), s.get('chunk_id')) for s in obs.sources}
    citation_ok = (
        bool(citations) and len(citations) == len(references)
        and all(1 <= i <= len(chunks) and
                (chunks[i - 1].get('document_id'), chunks[i - 1].get('chunk_id')) in source_ids
                for i in citations)
    )
    forbidden_ids = set(case.get('forbidden_document_ids', []))
    leaked = (any(c.get('document_id') in forbidden_ids for c in [*obs.chunks, *obs.sources])
              or any(word.lower() in obs.answer.lower()
                     for word in case.get('forbidden_keywords', [])))
    behavior = valid and detect_expected_behavior(obs.answer, case['expected_behavior'])
    if obs.retrieval_status in {'failed', 'not_run'}:
        failure = 'retrieval_' + obs.retrieval_status
    elif obs.answer_status != 'ok':
        failure = 'answer_' + obs.answer_status
    elif leaked:
        failure = 'permission_leak'
    elif normal and not rank:
        failure = 'retrieval_miss'
    elif normal and retrieved < 1:
        failure = 'retrieved_context_keyword_gap'
    elif normal and coverage < 1:
        failure = 'generation_keyword_gap'
    elif normal and not citation_ok:
        failure = 'citation_reference_invalid'
    elif not normal and not behavior:
        failure = 'behavior_marker_missing'
    else:
        failure = 'manual_review_required'
    return {'case': case, 'observation': asdict(obs), 'first_hit_rank': rank,
            'retrieval_keyword_coverage': retrieved, 'answer_keyword_coverage': coverage,
            'keyword_hit_count': len(hit), 'keyword_count': len(case['expected_keywords']),
            'keywords_hit': hit, 'keywords_missed': missed, 'behavior_marker_hit': behavior,
            'citation_reference_check': 'PASS' if valid and citation_ok else 'FAIL',
            'permission_check': ('FAIL' if leaked else 'PASS' if valid else 'BLOCKED')
                if forbidden_ids else 'NOT_APPLICABLE',
            'failure_mode': failure, 'semantic_review': 'PENDING',
            'factual_accuracy': 'NOT_MEASURED'}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    normal = [r for r in rows if r['case']['expected_behavior'] == 'answer']
    behavior = [r for r in rows if r['case']['expected_behavior'] != 'answer']
    total = sum(r['answer_keyword_coverage'] for r in normal)
    successful = [r for r in normal if r['observation']['answer_status'] == 'ok'
                  and r['observation']['retrieval_status'] in {'ok', 'empty'}]
    return {'total': len(rows), 'answer_denominator': len(normal), 'answer_coverage_sum': total,
            'avg_answer_keyword_coverage': total / len(normal) if normal else None,
            'successful_answer_count': len(successful),
            'success_only_coverage_diagnostic': total / len(successful) if successful else None,
            'retrieval_denominator': len(normal),
            **{f'top{k}_hit_rate':
               sum(0 < r['first_hit_rank'] <= k for r in normal) / len(normal)
               if normal else None for k in (1, 3, 5)},
            'mrr':
                sum(1 / r['first_hit_rank'] for r in normal if r['first_hit_rank']) / len(normal)
                if normal else None,
            'behavior_denominator': len(behavior),
            'behavior_marker_hits': sum(r['behavior_marker_hit'] for r in behavior),
            'citation_denominator': len(normal),
            'citation_reference_passes':
                sum(r['citation_reference_check'] == 'PASS' for r in normal),
            'permission_checks': dict(Counter(r['permission_check'] for r in rows)),
            'retrieval_status_counts':
                dict(Counter(r['observation']['retrieval_status'] for r in rows)),
            'answer_status_counts': dict(Counter(r['observation']['answer_status'] for r in rows)),
            'failure_mode_counts': dict(Counter(r['failure_mode'] for r in rows))}


def aggregate_report(cases: list[dict[str, Any]], observations: list[Observation],
                     provenance: dict[str, Any]) -> dict[str, Any]:
    ids = [case['query_id'] for case in cases]
    observed = [obs.query_id for obs in observations]
    if (len(set(ids)) != len(ids) or len(set(observed)) != len(observed)
            or not set(observed) <= set(ids)):
        raise ValueError('EVAL_CASE_ID_SET_INVALID')
    by_id = {obs.query_id: obs for obs in observations}
    rows = [score_sample(case, by_id.get(case['query_id'], Observation(case['query_id'])))
            for case in cases]
    suites = {suite: summarize([row for row in rows if row['case']['suite'] == suite])
              for suite in sorted({case['suite'] for case in cases})}
    incomplete = any(r['observation']['retrieval_status'] == 'not_run' or
                     r['observation']['answer_status'] in {'skipped', 'blocked'} for r in rows)
    numerical_ok = bool(suites) and all(s['answer_denominator'] > 0 and
        s['avg_answer_keyword_coverage'] >= .85 and s['top5_hit_rate'] >= .85
        and s['citation_reference_passes'] == s['citation_denominator']
        and s['behavior_marker_hits'] == s['behavior_denominator']
        and not any(s['permission_checks'].get(k, 0) for k in ('FAIL', 'BLOCKED'))
        and not any(s['answer_status_counts'].get(k, 0) for k in ('failed', 'empty'))
        for s in suites.values())
    return {'schema_version': 'rag-quality-v2', 'provenance': provenance,
            'total': len(rows), 'missing_observation_ids': sorted(set(ids) - set(observed)),
            'suites': suites,
            'by_scene': {key: summarize([r for r in rows if r['case']['scene'] == key])
                         for key in sorted({c['scene'] for c in cases})},
            'by_difficulty': {key: summarize([r for r in rows if r['case']['difficulty'] == key])
                              for key in sorted({c['difficulty'] for c in cases})},
            'mechanical_gate': 'BLOCKED' if incomplete else 'PASS' if numerical_ok else 'FAIL',
            'quality_acceptance': 'BLOCKED',
            'acceptance_blockers': ['ACCEPTED_C02_PROFILE_REQUIRED', 'SEMANTIC_REVIEW_REQUIRED',
                                    'FULL_RUNTIME_ACCEPTANCE_REQUIRED'],
            'formal_uat': False, 'release_evidence': False, 'release_allowed': False,
            'samples': rows}


def save_report_json(report: dict[str, Any], output: Path) -> None:
    """Exclusive creation only: preserve historical evidence, no cleanup or directories."""
    if not output.name.endswith('.json') or output.is_symlink():
        raise ValueError('EVAL_OUTPUT_INVALID')
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with output.open('x', encoding='utf-8') as stream:
        stream.write(content)
