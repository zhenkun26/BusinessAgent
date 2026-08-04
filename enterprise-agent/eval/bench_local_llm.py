"""本地小模型(qwen3.5:4b)各环节用时实测

复刻代码中两个本地模型调用点的真实调用形态,测量单次延迟:
1. planner 闲聊判断(app/graph/planner.py:_quick_chitchat_check)
   - prompt=planner_chitchat_detect,max_tokens=5
2. knowledge 答案自评(app/agents/knowledge.py:_generate_answer 自评段)
   - prompt=knowledge_llm_self_eval,max_tokens=10,answer 截 500 字

用法(需 Ollama 已启动且 qwen3.5:4b 已拉取):
    PYTHONIOENCODING=utf-8 python -m eval.bench_local_llm [runs]
"""

import sys
import time

from langchain_core.messages import HumanMessage

from app.prompts import get_prompt
from app.rag.llm import get_local_llm

# 与线上同形态的样本
_CHITCHAT_SAMPLES = [
    "你好",
    "今天心情不错",
    "销售提成政策是怎么规定的",  # 业务消息,应判"否"
]

_EVAL_QUERY = "销售提成政策是怎么规定的"
_EVAL_ANSWER = (
    "根据《销售政策》,销售提成按季度销售额阶梯计算:50 万以下部分提 5%,"
    "50-100 万部分提 7%,100 万以上部分提 8%。提成于次季度第一个月随工资发放,"
    "退货订单不计入提成基数。[来源1]"
)


def _bench(name: str, fn, runs: int) -> None:
    # 预热(含模型加载,不计入统计)
    t0 = time.perf_counter()
    fn()
    warmup = time.perf_counter() - t0

    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)

    avg = sum(times) / len(times)
    print(
        f"{name}: 预热(含冷加载) {warmup:.2f}s | "
        f"{runs} 次平均 {avg:.2f}s,最快 {min(times):.2f}s,最慢 {max(times):.2f}s"
    )


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    llm = get_local_llm()

    # 1. planner 闲聊判断(与 planner.py:152-162 同形态)
    chitchat_tpl, _ = get_prompt("planner_chitchat_detect")

    def chitchat():
        for msg in _CHITCHAT_SAMPLES:
            prompt = chitchat_tpl.format(message=msg)
            # 与 planner.py 同形态:ChatOllama 用 model_copy 改 num_predict
            llm.model_copy(update={"num_predict": 5}).invoke(
                [HumanMessage(content=prompt)]
            )

    _bench(f"闲聊判断(单次={len(_CHITCHAT_SAMPLES)} 条消息)", chitchat, runs)

    # 2. knowledge 答案自评(与 knowledge.py:266-273 同形态)
    eval_tpl, _ = get_prompt("knowledge_llm_self_eval")

    def self_eval():
        prompt = eval_tpl.format(query=_EVAL_QUERY, answer=_EVAL_ANSWER[:500])
        # 与 knowledge.py 同形态:ChatOllama 用 model_copy 改 num_predict
        llm.model_copy(update={"num_predict": 10}).invoke(
            [HumanMessage(content=prompt)]
        )

    _bench("答案自评(单次调用)", self_eval, runs)


if __name__ == "__main__":
    main()
