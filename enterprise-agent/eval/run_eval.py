"""C17 runtime evaluation. Default is an offline plan; --execute may call paid services.

Run from enterprise-agent: python -B -m eval.run_eval
Explicit runtime opt-in: --execute --output eval/results/UNIQUE.json
This entry never ingests, resets, migrates or creates collections. See docs/50-engineering/rag-quality.md.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any

from eval.rag_quality import Observation, aggregate_report, digest, load_corpus, save_report_json

ROOT = Path(__file__).resolve().parent


class CaptureRetrieval:
    """Capture the very same invocation consumed by KnowledgeAgent, including failures."""

    def __init__(self, chain: Any) -> None:
        self.chain = chain
        self.result: Any = None
        self.failed = False

    async def run(self, **kwargs: Any) -> Any:
        try:
            self.result = await self.chain.run(**kwargs)
            self.failed = bool(self.result.error)
            return self.result
        except Exception:
            self.failed = True
            raise


async def evaluate_case(
    case: dict[str, Any], agent: Any, *, no_answer: bool = False,
) -> Observation:
    obs = Observation(case['query_id'])
    capture = CaptureRetrieval(agent.degradation_chain)
    agent.degradation_chain = capture
    started = time.monotonic()
    try:
        if no_answer:
            await capture.run(query=case['query'], user_role=case['user_role'],
                              dept_namespace=case['user_dept'], top_k=5)
        else:
            result = await agent.run(case['query'])
            obs.answer = result.output.get('answer', '')
            obs.sources = [source.model_dump(mode='json') for source in result.sources]
            obs.decision = {key: result.output.get(key) for key in
                            ('coverage', 'stage', 'scene', 'threshold_used', 'decision_reason')}
            if result.error:
                obs.answer_status = 'failed'
                obs.error_code = 'EVAL_AGENT_FAILED'
            else:
                obs.answer_status = 'ok' if obs.answer.strip() else 'empty'
    except Exception:
        obs.answer_status = 'skipped' if no_answer else 'failed'
        obs.error_code = 'EVAL_RETRIEVAL_FAILED' if capture.failed else 'EVAL_AGENT_FAILED'
    finally:
        agent.degradation_chain = capture.chain
        obs.latency_ms = int((time.monotonic() - started) * 1000)
    if capture.result is not None:
        obs.stage = capture.result.stage
        obs.chunks = [asdict(chunk) for chunk in capture.result.results]
        obs.retrieval_status = 'failed' if capture.failed else 'ok' if obs.chunks else 'empty'
    else:
        obs.retrieval_status = 'failed'
    if obs.retrieval_status == 'failed':
        obs.answer_status = 'skipped' if no_answer else 'failed'
        obs.error_code = 'EVAL_RETRIEVAL_FAILED'
    return obs


def validate_published_corpus(manifest: dict[str, Any], rows: list[Any]) -> dict[str, str]:
    """Exact dedicated corpus, ACL and published snapshot; reject mixed/legacy stores."""
    expected = {doc['document_id']: doc for doc in manifest['documents']}
    if len(rows) != len(expected) or {row['document_id'] for row in rows} != set(expected):
        raise ValueError('EVAL_CORPUS_MEMBERSHIP')
    generations = {}
    for row in rows:
        doc = expected[row['document_id']]
        snapshot = row['published_snapshot']
        if (row['status'] != 'active' or row['state'] != 'published'
                or row['pending_publication'] is not None or not row['active_publication']
                or digest(row['content'].encode('utf-8')) != doc['sha256']
                or row['title'] != doc['title'] or row['dept_namespace'] != doc['dept_namespace']
                or set(row['access_roles']) != set(doc['access_roles'])
                or any(snapshot.get(key) != row[key] for key in
                       ('document_id', 'title', 'content', 'doc_type', 'dept_namespace',
                        'access_roles', 'uploaded_by', 'source_url'))):
            raise ValueError('EVAL_PUBLISHED_SOURCE_MISMATCH')
        generations[row['document_id']] = str(row['active_publication'])
    return generations


async def read_published_corpus(manifest: dict[str, Any]) -> dict[str, str]:
    from sqlalchemy import text
    from app.core.database import get_session_factory

    async with asyncio.timeout(10), get_session_factory()() as db:
        rows = (await db.execute(text('''SELECT d.*, p.state,
            p.snapshot AS published_snapshot FROM documents d
            LEFT JOIN knowledge_publications p ON p.publication_id = d.active_publication
                AND p.document_id = d.document_id
            ORDER BY d.document_id LIMIT 1001'''))).mappings().all()
    return validate_published_corpus(manifest, rows)


async def execute(manifest: dict[str, Any], cases: list[dict[str, Any]],
                  *, no_answer: bool = False) -> dict[str, Any]:
    # Imports deliberately occur only after explicit runtime opt-in.
    observations: list[Observation] = []
    provenance: dict[str, Any] = {
        'started_at': datetime.now(UTC).isoformat(), 'execution': 'runtime_requested',
        'manifest': manifest,
        'manifest_sha256': digest((ROOT / 'rag_quality_manifest.json').read_bytes()),
        'code_sha256': {str(p.relative_to(ROOT.parent)): digest(p.read_bytes())
                        for directory in ('app', 'eval')
                        for p in sorted((ROOT.parent / directory).rglob('*.py'))},
        'profile_acceptance': 'BLOCKED', 'no_answer': no_answer,
    }
    close_db = close_milvus = None
    try:
        from app.security.redaction import install_log_redaction
        install_log_redaction()
        from app.config import get_settings
        from app.rag.model_profile import PROFILE, validate_model_profile
        settings = get_settings()
        if (settings.model_profile != PROFILE or settings.vector_store_provider != 'milvus'
                or validate_model_profile(settings)):
            raise ValueError('EVAL_PROFILE_REQUIRED')
        provenance['model_config'] = {key: getattr(settings, key) for key in (
            'model_profile', 'embedding_provider', 'embedding_model', 'embedding_dim',
            'reranker_provider', 'reranker_model', 'llm_provider', 'lite_llm_model',
            'primary_llm_model', 'milvus_collection')}
        from app.core.database import init_db, close_db
        from app.core.milvus_client import init_milvus, close_milvus
        from app.agents.knowledge import KnowledgeAgent
        from app.security.rbac import AgentRole
        from app.prompts import (DEFAULT_PROMPTS, get_prompt, request_prompt_snapshot,
                                 set_prompt_user, reset_prompt_user)
        await init_db()
        generations = await read_published_corpus(manifest)
        provenance['publication_generations'] = generations
        await init_milvus(require_existing=True)
        token = set_prompt_user('c17-frozen-evaluation')
        try:
            async with request_prompt_snapshot():
                provenance['prompts'] = {}
                for name in sorted(DEFAULT_PROMPTS):
                    prompt, version = get_prompt(name)
                    provenance['prompts'][name] = {'version': version,
                                                   'sha256': digest(prompt.encode('utf-8'))}
                for case in cases:
                    # A changed corpus invalidates the run, even when individual scores look good.
                    if await read_published_corpus(manifest) != generations:
                        raise ValueError('EVAL_CORPUS_CHANGED')
                    agent = KnowledgeAgent(AgentRole(case['user_role']), case['user_dept'])
                    observations.append(await evaluate_case(case, agent, no_answer=no_answer))
                if await read_published_corpus(manifest) != generations:
                    raise ValueError('EVAL_CORPUS_CHANGED')
        finally:
            reset_prompt_user(token)
        provenance['runtime_status'] = 'EXECUTED'
    except Exception:
        # Keep prior rows and every unexecuted case; never export raw exceptions/configuration.
        provenance['runtime_status'] = 'BLOCKED'
        provenance['error_code'] = 'EVAL_RUNTIME_OR_PREFLIGHT_FAILED'
    finally:
        for close in (close_milvus, close_db):
            if close is not None:
                try:
                    await close()
                except Exception:
                    provenance['runtime_status'] = 'BLOCKED'
                    provenance['cleanup_status'] = 'CONNECTION_CLOSE_FAILED'
    provenance['finished_at'] = datetime.now(UTC).isoformat()
    report = aggregate_report(cases, observations, provenance)
    if provenance.get('runtime_status') != 'EXECUTED':
        report['mechanical_gate'] = 'BLOCKED'
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true',
                        help='Explicit paid-service/runtime opt-in')
    parser.add_argument('--no-answer', action='store_true',
                        help='Retrieval only; quality remains BLOCKED')
    parser.add_argument('--output', type=Path,
                        help='New JSON file in an existing evidence directory')
    args = parser.parse_args()
    manifest, cases = load_corpus(ROOT)
    if not args.execute:
        print(json.dumps({'status': 'BLOCKED', 'execution': 'NOT_RUN',
                          'primary_cases': manifest['primary']['count'],
                          'supplemental_cases': manifest['supplemental']['count'],
                          'reason': 'EXPLICIT_RUNTIME_OPT_IN_AND_ISOLATED_CORPUS_REQUIRED'}))
        return 2
    if (args.output is None or args.output.exists() or args.output.is_symlink()
            or args.output.suffix != '.json' or not args.output.parent.is_dir()
            or any(parent.is_symlink() for parent in args.output.parents)):
        parser.error('A fresh .json path in an existing non-symlink directory is required')
    report = asyncio.run(execute(manifest, cases, no_answer=args.no_answer))
    save_report_json(report, args.output)
    keys = ('total', 'mechanical_gate', 'quality_acceptance')
    print(json.dumps({key: report[key] for key in keys}))
    # Manual semantic review and accepted profile/runtime evidence cannot be fabricated by this CLI.
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
