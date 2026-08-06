"""eval/run_eval.py 答案层评测纯函数单元测试(rag-answer-quality)

覆盖:
- compute_keyword_coverage:两层(检索/答案)共用的关键词覆盖率机械口径
- detect_expected_behavior:对抗样本拒答/澄清特征词判定
- classify_failure_mode:失效模式三分类(检索未命中/组装遗漏/生成遗漏)
- aggregate_report:答案层聚合口径(生成失败与对抗样本不计入分子分母)
- save_report_json:结果落盘字段向后兼容(检索层既有字段保留,答案层字段新增)
"""

import json

from eval.run_eval import (
    SampleResult,
    aggregate_report,
    classify_failure_mode,
    compute_keyword_coverage,
    detect_expected_behavior,
    evaluate_answer,
    save_report_json,
)


def _make_sample(**overrides) -> SampleResult:
    """构造一条默认"全命中"样本,按需覆盖字段"""
    defaults = {
        "query_id": "Q900",
        "query": "测试问题",
        "ground_truth_doc": "销售政策",
        "ground_truth_section": "1.1",
        "expected_keywords": ["24小时", "CRM"],
        "scene": "factual",
        "difficulty": "easy",
        "hit_at_5": True,
        "hit_at_1": True,
        "reciprocal_rank": 1.0,
        "keyword_coverage": 1.0,
        "answer_status": "ok",
        "answer": "需在24小时内在CRM创建跟进任务",
        "answer_keyword_coverage": 1.0,
    }
    defaults.update(overrides)
    return SampleResult(**defaults)


def test_should_return_partial_coverage_when_some_keywords_missing():
    # Given: 文本只包含部分关键词
    text = "新客户需在24小时内创建跟进任务"
    # When: 计算覆盖率
    coverage, hit, missed = compute_keyword_coverage(text, ["24小时", "CRM"])
    # Then: 命中 1/2,遗漏词正确列出
    assert coverage == 0.5
    assert hit == ["24小时"]
    assert missed == ["CRM"]


def test_should_match_case_insensitively_when_keywords_differ_in_case():
    # Given: 文本与关键词大小写不同
    # When/Then: 大小写不敏感命中
    coverage, hit, missed = compute_keyword_coverage("在 crm 系统建单", ["CRM"])
    assert coverage == 1.0
    assert hit == ["CRM"]
    assert missed == []


def test_should_return_zero_coverage_when_keywords_empty():
    # Given/When/Then: 无关键词时覆盖率为 0 且不抛异常
    assert compute_keyword_coverage("任意文本", []) == (0.0, [], [])


def test_should_detect_refusal_when_answer_contains_refusal_marker():
    # Given: 答案包含拒答特征词
    answer = "现有知识库未覆盖该情形，建议联系相关业务负责人核实。"
    # When/Then: 拒答样本判定命中
    assert detect_expected_behavior(answer, "refuse") is True


def test_should_not_detect_refusal_when_answer_is_normal():
    # Given: 正常作答文本
    answer = "新客户需在24小时内创建跟进任务[来源1]"
    # When/Then: 不误判为拒答
    assert detect_expected_behavior(answer, "refuse") is False


def test_should_detect_clarify_when_answer_contains_clarify_marker():
    # Given: 答案包含澄清特征词
    answer = "请问您指的是哪个部门的报销政策？请补充说明。"
    # When/Then: 澄清样本判定命中
    assert detect_expected_behavior(answer, "clarify") is True


def test_should_classify_retrieval_miss_when_doc_not_in_top5():
    # Given: 检索未命中 ground_truth_doc
    sr = _make_sample(hit_at_5=False, keyword_coverage=0.0, answer_keyword_coverage=0.0)
    # When/Then: 归因检索未命中
    assert classify_failure_mode(sr) == "retrieval_miss"


def test_should_classify_assembly_omission_when_keywords_missing_from_context():
    # Given: 检索命中但关键词未全部进入 Top-5 上下文
    sr = _make_sample(keyword_coverage=0.5, answer_keyword_coverage=0.5)
    # When/Then: 归因上下文组装遗漏
    assert classify_failure_mode(sr) == "assembly_omission"


def test_should_classify_generation_omission_when_context_full_but_answer_missing():
    # Given: 上下文已覆盖全部关键词但答案遗漏
    sr = _make_sample(keyword_coverage=1.0, answer_keyword_coverage=0.5)
    # When/Then: 归因生成遗漏
    assert classify_failure_mode(sr) == "generation_omission"


def test_should_not_classify_adversarial_sample():
    # Given: 对抗样本(预期拒答)
    sr = _make_sample(expected_behavior="refuse", hit_at_5=False)
    # When/Then: 不参与三分类
    assert classify_failure_mode(sr) == ""


def test_should_exclude_failed_and_adversarial_from_answer_coverage_when_aggregating():
    # Given: 1 条正常作答(覆盖 0.5)、1 条生成失败、1 条对抗样本(行为命中)
    ok = _make_sample(query_id="Q901", answer_keyword_coverage=0.5)
    failed = _make_sample(query_id="Q902", answer_status="failed", answer_keyword_coverage=0.0)
    adversarial = _make_sample(
        query_id="Q903",
        expected_behavior="refuse",
        answer_status="ok",
        behavior_detected=True,
        answer_keyword_coverage=0.0,
    )
    # When: 聚合
    report = aggregate_report([ok, failed, adversarial])
    # Then: 只有 1 条计入答案层分子分母,对抗样本单独统计
    assert report.answer_evaluated == 1
    assert report.answer_failed == 1
    assert report.avg_answer_keyword_coverage == 0.5
    assert report.adversarial_total == 1
    assert report.adversarial_correct == 1


def test_should_count_failure_mode_stats_when_aggregating():
    # Given: 三种失效模式各一条
    r1 = _make_sample(query_id="Q910", hit_at_5=False, keyword_coverage=0.0,
                      answer_keyword_coverage=0.0, failure_mode="retrieval_miss")
    r2 = _make_sample(query_id="Q911", keyword_coverage=0.5, answer_keyword_coverage=0.5,
                      failure_mode="assembly_omission")
    r3 = _make_sample(query_id="Q912", keyword_coverage=1.0, answer_keyword_coverage=0.5,
                      failure_mode="generation_omission")
    # When: 聚合
    report = aggregate_report([r1, r2, r3])
    # Then: 三类各计 1
    assert report.failure_mode_stats == {
        "retrieval_miss": 1,
        "assembly_omission": 1,
        "generation_omission": 1,
    }


def test_should_keep_legacy_fields_and_add_answer_fields_when_saving_json(tmp_path):
    # Given: 一条带答案层结果的样本
    report = aggregate_report([_make_sample()])
    output = tmp_path / "latest.json"
    # When: 落盘
    save_report_json(report, output)
    data = json.loads(output.read_text(encoding="utf-8"))
    # Then: 检索层既有字段保持兼容
    for key in ["total", "top1_hit_rate", "top3_hit_rate", "top5_hit_rate",
                "mrr", "avg_keyword_coverage", "avg_latency_ms",
                "by_scene", "by_difficulty", "samples"]:
        assert key in data
    # And: 答案层新增字段并列
    for key in ["avg_answer_keyword_coverage", "answer_evaluated", "answer_failed",
                "adversarial_total", "adversarial_correct", "failure_mode_stats"]:
        assert key in data
    # And: 逐样本诊断字段齐备(检索命中/上下文内容/生成答案)
    sample = data["samples"][0]
    for key in ["top_k_chunks", "answer", "answer_status",
                "answer_keyword_coverage", "failure_mode"]:
        assert key in sample


async def test_should_mark_refusal_when_adversarial_sample_has_no_chunks():
    # Given: 对抗样本(预期拒答)且检索结果为空(线上链路直接返回固定拒答文案)
    sr = _make_sample(
        expected_behavior="refuse",
        expected_keywords=[],
        top_k_chunks=[],
        hit_at_5=False,
        answer_status="skipped",
        answer="",
    )
    # When: 答案层评测(不调用 LLM)
    sr = await evaluate_answer(sr)
    # Then: 复现线上固定拒答文案并判定行为命中
    assert sr.answer_status == "ok"
    assert sr.answer == "未在知识库中找到相关信息。"
    assert sr.behavior_detected is True


def test_should_exclude_keywordless_adversarial_from_coverage_when_aggregating():
    # Given: 1 条有关键词样本(覆盖 0.5)+ 1 条无关键词对抗样本
    rated = _make_sample(query_id="Q920", keyword_coverage=0.5)
    adversarial = _make_sample(
        query_id="Q921", expected_behavior="refuse", expected_keywords=[], keyword_coverage=0.0
    )
    # When: 聚合
    report = aggregate_report([rated, adversarial])
    # Then: 检索层关键词覆盖率只按有关键词的样本计
    assert report.avg_keyword_coverage == 0.5
