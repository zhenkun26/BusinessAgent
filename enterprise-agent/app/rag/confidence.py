"""置信度决策器(对应 v3 方案 P1-2 场景化阈值)

策略:
- 场景化阈值:政策类(policy)0.8 / 事实类(factual)0.6 / 推理类(inferential)0.5
- <reject_min(0.2):直接拒绝,返回"未找到相关信息"
- ≥accept_skip(0.9):跳过人工提示,直接返回答案
- 中间区间:返回答案 + 提示用户核实

返回 coverage 状态:
- "none":     < reject_min,拒绝
- "partial":  reject_min ≤ score < scene_threshold,返回 + 提示人工核实
- "full":     ≥ scene_threshold,直接返回
- "high":     ≥ accept_skip,跳过人工提示
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from loguru import logger


class Coverage(str, Enum):
    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"
    HIGH = "high"


@dataclass
class ConfidenceDecision:
    """置信度决策结果"""

    coverage: Coverage
    score: float
    threshold_used: float
    action: str  # "reject" | "answer_with_hint" | "answer" | "answer_skip_hint"
    reason: Optional[str] = None


# 场景化阈值表
SCENE_THRESHOLDS: dict[str, float] = {
    "policy": 0.8,        # 政策类:严格,必须高置信度
    "factual": 0.6,       # 事实类:中等
    "inferential": 0.5,   # 推理类:宽松(允许模型推断)
    "default": 0.6,
}

# 拒绝下限 & 跳过上限
REJECT_MIN = 0.2
ACCEPT_SKIP = 0.9


class ConfidenceDecider:
    """场景化置信度决策器"""

    def __init__(
        self,
        scene_thresholds: Optional[dict[str, float]] = None,
        reject_min: float = REJECT_MIN,
        accept_skip: float = ACCEPT_SKIP,
    ):
        self.thresholds = scene_thresholds or SCENE_THRESHOLDS
        self.reject_min = reject_min
        self.accept_skip = accept_skip

    def decide(
        self,
        score: float,
        scene: str = "default",
    ) -> ConfidenceDecision:
        """根据分数 + 场景给出决策

        Args:
            score: 综合置信度(检索分数 + LLM 自评的加权)
            scene: 场景类型(policy/factual/inferential)
        """
        threshold = self.thresholds.get(scene, self.thresholds["default"])
        score = max(0.0, min(1.0, score))

        if score < self.reject_min:
            return ConfidenceDecision(
                coverage=Coverage.NONE,
                score=score,
                threshold_used=threshold,
                action="reject",
                reason=f"置信度 {score:.2f} < 拒绝下限 {self.reject_min}",
            )

        if score >= self.accept_skip:
            return ConfidenceDecision(
                coverage=Coverage.HIGH,
                score=score,
                threshold_used=threshold,
                action="answer_skip_hint",
                reason=f"置信度 {score:.2f} ≥ 跳过上限 {self.accept_skip}",
            )

        if score >= threshold:
            return ConfidenceDecision(
                coverage=Coverage.FULL,
                score=score,
                threshold_used=threshold,
                action="answer",
                reason=f"置信度 {score:.2f} ≥ 场景阈值 {threshold}({scene})",
            )

        # 中间区间
        return ConfidenceDecision(
            coverage=Coverage.PARTIAL,
            score=score,
            threshold_used=threshold,
            action="answer_with_hint",
            reason=f"置信度 {score:.2f} 介于 [{self.reject_min}, {threshold})({scene})",
        )

    @staticmethod
    def detect_scene(query: str) -> str:
        """简单场景识别(规则版,后续可换 LLM 分类)

        政策类关键词:政策/规定/标准/流程/审批/权限/要求/必须/应该
        推理类关键词:为什么/如何分析/推测/影响/原因/对比
        其余按事实类
        """
        policy_kw = {"政策", "规定", "标准", "流程", "审批", "权限", "要求", "必须", "应该", "申请"}
        infer_kw = {"为什么", "如何分析", "推测", "影响", "原因", "对比", "分析", "策略"}

        for kw in policy_kw:
            if kw in query:
                return "policy"
        for kw in infer_kw:
            if kw in query:
                return "inferential"
        return "factual"

    @staticmethod
    def combine_score(
        retrieval_score: float,
        llm_self_score: Optional[float] = None,
        retrieval_weight: float = 0.6,
    ) -> float:
        """综合置信度计算

        retrieval_score: Top-1 检索分数(0-1)
        llm_self_score: LLM 自评(0-1),None 时只用检索分
        retrieval_weight: 检索分权重
        """
        if llm_self_score is None:
            return max(0.0, min(1.0, retrieval_score))
        llm_w = 1.0 - retrieval_weight
        return max(0.0, min(1.0, retrieval_score * retrieval_weight + llm_self_score * llm_w))
