"""压测报告渲染器:把 k6 summary JSON 转成 Markdown 压测报告(load-test-and-dr-drill / tasks 1.3)

用法(通常由 eval/run_load_test.sh 调用):
    python3 eval/render_load_report.py \
        --summary eval/results/loadtest_summary_<ts>.json \
        --profile formal --base-url http://localhost:8000 --k6-exit 0 \
        --out eval/results/loadtest_report_<ts>.md

报告骨架含:环境配置 / 阶梯与判定 / 各接口实测 p95/p99/错误率 / 瓶颈分析(自动标注超限项)。
瓶颈分析与 SLA 校准结论的定性部分由执行人在正式压测后补写。
"""

import argparse
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# SLA 初值(production-readiness 规格):核心接口 p95 ≤ 2s、p99 ≤ 5s、错误率 < 0.5%
SLA = {"p95_ms": 2000.0, "p99_ms": 5000.0, "error_rate": 0.005}


def _env_info() -> dict:
    info = {
        "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "cpu_cores": os.cpu_count() or "?",
        "python": platform.python_version(),
    }
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}} ({{.Status}})"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            info["docker_containers"] = out.stdout.strip().splitlines()
    except Exception:
        pass
    return info


def _endpoint_metrics(summary: dict) -> dict:
    """从 k6 summary 提取按 endpoint 分组的 http_req_duration / http_req_failed。"""
    metrics = summary.get("metrics", {})
    result: dict[str, dict] = {}
    dur = metrics.get("http_req_duration", {})
    failed = metrics.get("http_req_failed", {})
    # k6 summary 的 values 含 p(95)/p(99);分组值在 thresholds 对应的子指标里。
    # 简化口径:整体值 + 各 endpoint 的阈值通过情况由 thresholds 段读取。
    result["_overall"] = {
        "p95_ms": dur.get("values", {}).get("p(95)"),
        "p99_ms": dur.get("values", {}).get("p(99)"),
        "avg_ms": dur.get("values", {}).get("avg"),
        "max_ms": dur.get("values", {}).get("max"),
        "error_rate": failed.get("values", {}).get("rate"),
        "requests": metrics.get("http_reqs", {}).get("values", {}).get("count"),
    }
    return result


def _threshold_rows(summary: dict) -> list[tuple[str, bool]]:
    rows = []
    for name, item in (summary.get("metrics") or {}).items():
        for thr, res in (item.get("thresholds") or {}).items():
            rows.append((f"{name} :: {thr}", bool(res.get("ok"))))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--k6-exit", type=int, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    env = _env_info()
    overall = _endpoint_metrics(summary)["_overall"]
    thresholds = _threshold_rows(summary)
    all_ok = args.k6_exit == 0 and all(ok for _, ok in thresholds)

    def fmt_ms(v: float | None) -> str:
        return f"{v:.0f} ms" if isinstance(v, (int, float)) else "N/A"

    def fmt_rate(v: float | None) -> str:
        return f"{v * 100:.3f}%" if isinstance(v, (int, float)) else "N/A"

    breaches = [name for name, ok in thresholds if not ok]

    lines = [
        "# 阶梯压测报告",
        "",
        f"- 执行时间:{env['time_utc']}",
        f"- 档位:`{args.profile}`(formal=正式阶梯;smoke=脚本链路冒烟)",
        f"- 目标:`{args.base_url}`",
        f"- 总体判定:**{'达标' if all_ok else '未达标'}**(k6 退出码 {args.k6_exit})",
        "",
        "## 1. 环境配置",
        "",
        f"- OS:{env['os']},CPU {env['cpu_cores']} 核",
        "- 部署形态:单机 Docker Compose(容器清单见下);API 进程模型与 worker 数见启动命令",
        "- 模型路径 / LLM 供应:以执行环境 .env 为准(报告正文应补充是否命中云端限流)",
        "",
        "```",
        *env.get("docker_containers", ["(docker 不可用或未运行)"]),
        "```",
        "",
        "## 2. SLA 达标线与口径",
        "",
        f"- 达标线(production-readiness 初值):p95 ≤ {SLA['p95_ms']:.0f} ms、"
        f"p99 ≤ {SLA['p99_ms']:.0f} ms、错误率 < {SLA['error_rate'] * 100:.1f}%",
        "- 口径备注:SLA 对对话类接口以「首 token」计,本脚本量的是完整响应时长(更严口径)",
        "",
        "## 3. 实测指标(整体)",
        "",
        "| 指标 | 实测值 | SLA 达标线 |",
        "|---|---|---|",
        f"| 请求总数 | {overall['requests'] if overall['requests'] is not None else 'N/A'} | - |",
        f"| p95 | {fmt_ms(overall['p95_ms'])} | ≤ 2000 ms |",
        f"| p99 | {fmt_ms(overall['p99_ms'])} | ≤ 5000 ms |",
        f"| avg | {fmt_ms(overall['avg_ms'])} | - |",
        f"| max | {fmt_ms(overall['max_ms'])} | - |",
        f"| 错误率 | {fmt_rate(overall['error_rate'])} | < 0.5% |",
        "",
        "> 分接口(health / chat)的 p95/p99/错误率以 k6 summary 的分组指标为准,",
        "> 原始数据见同名 `loadtest_summary_*.json`。",
        "",
        "## 4. 阈值判定明细",
        "",
        "| 阈值 | 结果 |",
        "|---|---|",
        *[f"| `{name}` | {'✅ 通过' if ok else '❌ 未达标'} |" for name, ok in thresholds],
        "",
        "## 5. 瓶颈分析",
        "",
    ]
    if breaches:
        lines += [
            "本次压测存在未达标项:",
            "",
            *[f"- `{b}`" for b in breaches],
            "",
            "待执行人补充定位:云端 LLM rate limit / uvicorn worker / Milvus 内存 / 本机资源争用。",
        ]
    else:
        lines += [
            "全部阈值达标。待执行人补充:瓶颈最接近的资源项与下一档并发预估。",
        ]
    lines += [
        "",
        "## 6. SLA 校准结论(回访 production-readiness 初值)",
        "",
        "<!-- 正式压测后填写:确认 SLA 初值达标 / 提出校准变更及依据,",
        "     供 production-readiness-baseline 归档消化;同步关闭 ISSUES I-01。 -->",
        "",
        "待定稿。",
        "",
    ]

    Path(args.out).write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
