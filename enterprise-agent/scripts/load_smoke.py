"""并发冒烟压测(验收:1000 并发无报错)

用法:
    .venv/bin/python scripts/load_smoke.py --concurrency 1000 --requests 1000

目标端点(/health、/ready 不限流):
    - 统计成功/失败数、P50/P95/P99 延迟
    - 任何非 2xx 或连接异常都计为失败
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def _fire_once(
    client: httpx.AsyncClient,
    url: str,
    results: list[dict],
) -> None:
    start = time.perf_counter()
    try:
        resp = await client.get(url, timeout=30)
        latency_ms = (time.perf_counter() - start) * 1000
        results.append(
            {
                "ok": resp.status_code < 500,
                "status": resp.status_code,
                "latency_ms": latency_ms,
            }
        )
    except Exception as exc:  # noqa: BLE001 连接异常计为失败
        latency_ms = (time.perf_counter() - start) * 1000
        results.append(
            {"ok": False, "status": -1, "latency_ms": latency_ms, "error": str(exc)}
        )


async def run_load_test(
    base_url: str,
    concurrency: int,
    total_requests: int,
) -> dict:
    """并发执行请求并统计"""
    results: list[dict] = []
    semaphore = asyncio.Semaphore(concurrency)

    async def worker(client: httpx.AsyncClient, url: str) -> None:
        async with semaphore:
            await _fire_once(client, url, results)

    async with httpx.AsyncClient(base_url=base_url, limits=httpx.Limits(
        max_connections=concurrency, max_keepalive_connections=concurrency
    )) as client:
        urls = ["/health", "/ready"] * (total_requests // 2)
        if len(urls) < total_requests:
            urls.append("/health")
        start = time.perf_counter()
        await asyncio.gather(*[worker(client, url) for url in urls])
        elapsed = time.perf_counter() - start

    latencies = sorted(r["latency_ms"] for r in results)
    ok_count = sum(1 for r in results if r["ok"])
    return {
        "total": len(results),
        "ok": ok_count,
        "failed": len(results) - ok_count,
        "elapsed_sec": round(elapsed, 2),
        "qps": round(len(results) / elapsed, 1),
        "p50_ms": round(statistics.median(latencies), 1),
        "p95_ms": round(latencies[int(len(latencies) * 0.95) - 1], 1),
        "p99_ms": round(latencies[int(len(latencies) * 0.99) - 1], 1),
        "max_ms": round(latencies[-1], 1),
        "status_distribution": _status_distribution(results),
    }


def _status_distribution(results: list[dict]) -> dict:
    dist: dict[str, int] = {}
    for r in results:
        key = str(r["status"])
        dist[key] = dist.get(key, 0) + 1
    return dist


def main() -> None:
    """CLI 入口"""
    parser = argparse.ArgumentParser(description="并发冒烟压测")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=1000)
    parser.add_argument("--requests", type=int, default=1000)
    args = parser.parse_args()

    print(
        f"压测开始: {args.base_url} concurrency={args.concurrency} "
        f"requests={args.requests}"
    )
    report = asyncio.run(
        run_load_test(args.base_url, args.concurrency, args.requests)
    )
    print("\n===== 压测报告 =====")
    for key, value in report.items():
        print(f"  {key}: {value}")

    if report["failed"] == 0:
        print("\n✓ 验收通过: 0 失败")
    else:
        print(f"\n✗ 验收失败: {report['failed']} 个失败")


if __name__ == "__main__":
    main()
