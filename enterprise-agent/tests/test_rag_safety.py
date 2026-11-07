"""Synthetic negative controls and actual-source characterization; no provider calls."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
from typing import Any
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
HELPERS = runpy.run_path(str(ROOT / "tests/test_credential_safety.py"))
load, module, function = HELPERS["load"], HELPERS["module"], HELPERS["function"]
safety = load("f206_safety", "eval/rag_safety.py")
cases = safety.load_cases()


class SafetyControlTests(unittest.TestCase):
    def test_positive_and_negative_controls_are_independent(self) -> None:
        report = safety.verify_controls()
        self.assertEqual(report["checker_verification"], "PASS")
        self.assertEqual(report["safe_controls"]["case_denominator"], 8)
        self.assertEqual(report["safe_controls"]["mechanical_pass_count"], 8)
        self.assertEqual(report["unsafe_controls"]["mechanical_pass_count"], 0)
        self.assertEqual(report["unexpected_negative_case_ids"], [])

    def test_frozen_c17_corpus_and_denominators_stay_separate(self) -> None:
        quality = module("f206_c17", __file__=str(ROOT / "eval/rag_quality.py"))
        with patch.dict(sys.modules, {"f206_c17": quality}):
            exec(compile((ROOT / "eval/rag_quality.py").read_bytes(),
                         quality.__file__, "exec"), quality.__dict__)
        manifest, original = quality.load_corpus(ROOT / "eval")
        self.assertEqual(len(original), 128)
        self.assertEqual(len(manifest["documents"]), 9)
        report = quality.aggregate_report(original, [], {})
        for suite, answers, behavior in (("primary", 115, 7), ("supplemental", 2, 4)):
            self.assertEqual(report["suites"][suite]["answer_denominator"], answers)
            self.assertEqual(report["suites"][suite]["behavior_denominator"], behavior)
        self.assertTrue(set(safety.CASE_IDS).isdisjoint(c["query_id"] for c in original))

    def test_every_case_has_explicit_source_and_review_evidence(self) -> None:
        report = safety.verify_controls()
        for row, case in zip(report["unsafe_controls"]["samples"], cases, strict=True):
            with self.subTest(case=case["case_id"]):
                self.assertEqual(row["input"], case)
                self.assertEqual(row["observation"]["answer"], case["unsafe_answer"])
                self.assertEqual(set(row["failures"]), set(case["unsafe_expected_failures"]))
                self.assertEqual(row["semantic_review"], "PENDING")

    def test_missing_observations_never_shrink_denominator(self) -> None:
        for observations, passed in (([], 0), (safety.control_observations(cases, "safe")[:1], 1)):
            report = safety.build_report(observations)
            self.assertEqual(len(report["samples"]), 8)
            self.assertEqual(report["case_denominator"], 8)
            self.assertEqual(report["mechanical_pass_count"], passed)
            self.assertEqual(len(report["missing_case_ids"]), 8 - passed)
            self.assertEqual(report["mechanical_gate"], "FAIL")

    def test_failed_skipped_empty_and_not_run_have_no_credit(self) -> None:
        for status in ("failed", "skipped", "empty", "not_run"):
            observations = safety.control_observations(cases, "safe")
            observations[0]["status"] = status
            with self.subTest(status=status):
                report = safety.build_report(observations)
                self.assertEqual(report["mechanical_pass_count"], 7)
                self.assertIn("observation_" + status, report["samples"][0]["failures"])
                self.assertEqual(report["samples"][0]["citation_reference_check"], "FAIL")

    def test_ok_but_blank_answer_has_no_credit(self) -> None:
        for answer in ("", "  \n"):
            observations = safety.control_observations(cases, "safe")
            observations[0]["answer"] = answer
            self.assertIn("observation_empty",
                          safety.build_report(observations)["samples"][0]["failures"])

    def test_duplicate_unknown_and_non_list_observations_rejected(self) -> None:
        observations = safety.control_observations(cases, "safe")
        for invalid in (observations + observations[:1],
                        [{**observations[0], "case_id": "UNKNOWN"}], {}):
            with self.assertRaises(ValueError):
                safety.build_report(invalid)

    def test_malformed_observations_rejected(self) -> None:
        original = safety.control_observations(cases, "safe")[0]
        invalids = [None, {}, {**original, "extra": 1},
                    {**original, "case_id": []}, {**original, "status": []},
                    {**original, "status": "SUCCESS"}, {**original, "answer": None},
                    {**original, "sources": {}}, {**original, "sources": ["bad"]},
                    {**original, "sources": [{"document_id": [], "chunk_id": "x"}]},
                    {**original, "sources": [{"document_id": "", "chunk_id": "x"}]},
                    {**original, "sources": original["sources"] * 2}]
        for invalid in invalids:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                safety.build_report([invalid])

    def test_invalid_citations_fail_even_with_valid_reference_alongside(self) -> None:
        for reference in ("", "[来源0]", "[来源2]", "[来源x]", "[来源１]",
                          "[来源1] [来源2]", "[来源1] [来源", "[来源1] [来源x]",
                          "[来源" + "9" * 5000 + "]"):
            obs = safety.control_observations(cases, "safe")[:1]
            obs[0]["answer"] = "7 days " + reference
            with self.subTest(reference=reference[:40]):
                self.assertIn("citation_reference_invalid",
                              safety.build_report(obs)["samples"][0]["failures"])

    def test_missing_wrong_and_extraneous_source_identity_fail(self) -> None:
        original = safety.control_observations(cases, "safe")[0]
        for sources in ([], [{"document_id": "other", "chunk_id": "PI01-chunk"}],
                        [{"document_id": "synthetic-policy", "chunk_id": "other"}],
                        original["sources"] + [{"document_id": "other", "chunk_id": "other"}]):
            obs = {**original, "sources": sources}
            with self.subTest(sources=sources):
                self.assertIn("citation_reference_invalid",
                              safety.build_report([obs])["samples"][0]["failures"])

    def test_valid_numbering_does_not_establish_support(self) -> None:
        report = safety.build_report(safety.control_observations(cases, "unsafe"))
        row = report["samples"][-1]
        self.assertEqual(row["citation_reference_check"], "PASS")
        self.assertEqual(row["mechanical_check"], "FAIL")
        self.assertEqual(row["semantic_review"], "PENDING")
        self.assertEqual(row["factual_accuracy"], "NOT_MEASURED")

    def test_unlisted_fabrication_exposes_literal_probe_limit(self) -> None:
        obs = safety.control_observations(cases, "safe")
        obs[-1]["answer"] = "7 days plus a free fictional spaceship. [来源1]"
        report = safety.build_report(obs)
        self.assertEqual(report["mechanical_gate"], "PASS")
        self.assertEqual(report["model_robustness"], "NOT_MEASURED")
        self.assertEqual(report["quality_acceptance"], "BLOCKED")
        self.assertFalse(report["actual_pipeline_executed"])

    def test_refusal_marker_does_not_hide_known_fabrication(self) -> None:
        report = safety.build_report(safety.control_observations(cases, "unsafe"))
        row = report["samples"][5]
        self.assertEqual(row["required_literals_missing"], [])
        self.assertEqual(row["citation_reference_check"], "PASS")
        self.assertIn("forbidden_literal", row["failures"])

    def test_no_answer_cannot_invent_citations_or_sources(self) -> None:
        obs = safety.control_observations(cases, "safe")
        obs[5]["answer"] += " [来源1]"
        self.assertIn("citation_reference_invalid",
                      safety.build_report(obs)["samples"][5]["failures"])
        obs = safety.control_observations(cases, "safe")
        obs[5]["sources"] = deepcopy(obs[0]["sources"])
        self.assertIn("citation_reference_invalid",
                      safety.build_report(obs)["samples"][5]["failures"])

    def test_inputs_not_mutated_and_evidence_detached(self) -> None:
        obs = safety.control_observations(cases, "safe")
        before = deepcopy(obs)
        report = safety.build_report(obs)
        self.assertEqual(obs, before)
        obs[0]["sources"][0]["document_id"] = "changed"
        self.assertEqual(report["samples"][0]["observation"], before[0])

    def test_corpus_drift_rejected_and_provenance_matches_bytes(self) -> None:
        read = Path.read_bytes
        with patch.object(Path, "read_bytes", lambda p: b"changed" if p == safety.CORPUS else read(p)):
            with self.assertRaisesRegex(ValueError, "CORPUS_CHANGED"):
                safety.load_cases()
        report = safety.build_report([])
        for relative, digest in report["provenance"].items():
            self.assertEqual(digest, hashlib.sha256((ROOT / relative).read_bytes()).hexdigest())

    def test_unknown_control_variant_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "CONTROL_VARIANT"):
            safety.control_observations(cases, "live")

    def test_read_only_entry_guard_denies_side_effects(self) -> None:
        entry = runpy.run_path(str(ROOT / "eval/run_f206_rag_safety.py"))
        for event, args in (("socket.connect", ()), ("subprocess.Popen", ()),
                            ("os.remove", ()), ("os.mkdir", ()), ("os.rename", ()),
                            ("open", ("synthetic", "w", 1))):
            with self.subTest(event=event), self.assertRaises(RuntimeError):
                entry["guard"](event, args)
        entry["guard"]("open", ("synthetic", "r", 0))


class ActualGenerationCharacterizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_untrusted_inputs_and_authored_unsafe_outputs_pass_through(self) -> None:
        defaults = runpy.run_path(str(ROOT / "app/prompts/defaults.py"))
        for case in cases[:4]:
            with self.subTest(case=case["case_id"]):
                chain = NS(ainvoke=AsyncMock(return_value=NS(content=case["unsafe_answer"])))
                target = function("app/agents/knowledge.py", "_generate_answer",
                    {"logger": Mock(), "get_lite_llm": lambda: chain,
                     "get_prompt": lambda name: (defaults["KNOWLEDGE_RAG_ANSWER"], 0)},
                    "KnowledgeAgent")
                owner = NS(_get_eval_llm=Mock(side_effect=AssertionError("NO_MODEL_ALLOWED")))
                answer, self_score = await target(owner, case["query"],
                    [NS(**chunk, score=.95) for chunk in case["chunks"]], case["history"])
                import json
                messages = chain.ainvoke.call_args.args[0]
                sent = json.loads(messages[1].content)
                self.assertEqual(messages[0].type, "system")
                self.assertEqual(messages[1].type, "human")
                self.assertEqual(case["chunks"][0]["title"], sent["context"][0]["title"])
                self.assertEqual(case["chunks"][0]["content"], sent["context"][0]["body"])
                self.assertEqual(case["query"], sent["query"])
                self.assertEqual(case["history"], sent["history"])
                self.assertNotIn(case["chunks"][0]["content"], messages[0].content)
                self.assertEqual(chain.ainvoke.call_args.kwargs["config"]["metadata"]["prompt_version"], 0)
                self.assertEqual(answer, case["unsafe_answer"])
                self.assertIsNone(self_score)
                owner._get_eval_llm.assert_not_called()
                chain.ainvoke.assert_awaited_once()
                # A stub returning an attack phrase is a propagation diagnostic, not model behavior.
                obs = safety.control_observations(cases, "safe")
                next(o for o in obs if o["case_id"] == case["case_id"])["answer"] = answer
                self.assertEqual(safety.build_report(obs)["mechanical_pass_count"], 7)


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    unittest.main(verbosity=2)
