#!/bin/bash
# 阶梯压测执行入口(load-test-and-dr-drill / tasks 1.2/1.3)
#
# 用法:
#   eval/run_load_test.sh                # formal 档,打 http://localhost:8000
#   PROFILE=smoke eval/run_load_test.sh  # 冒烟档,验证脚本链路
#   BASE_URL=http://host:8000 eval/run_load_test.sh
#
# 行为:
#   1. 优先用本机 k6;无 k6 时退回 docker grafana/k6 镜像(BASE_URL 自动改写为 host.docker.internal)
#   2. summary JSON 落 eval/results/loadtest_summary_<ts>.json
#   3. 调用 eval/render_load_report.py 生成 Markdown 压测报告 eval/results/loadtest_report_<ts>.md
#   4. k6 thresholds 未达标 → 非零退出(报告仍生成)
set -uo pipefail

cd "$(dirname "$0")/.."
TS=$(date +%Y%m%d_%H%M%S)
PROFILE=${PROFILE:-formal}
BASE_URL=${BASE_URL:-http://localhost:8000}
SUMMARY_JSON="eval/results/loadtest_summary_${TS}.json"
REPORT_MD="eval/results/loadtest_report_${TS}.md"
mkdir -p eval/results

if command -v k6 >/dev/null 2>&1; then
  echo "[run_load_test] 使用本机 k6: $(k6 version)"
  K6_CMD=(k6 run)
  K6_BASE_URL="$BASE_URL"
elif command -v docker >/dev/null 2>&1; then
  echo "[run_load_test] 本机无 k6,退回 docker grafana/k6 镜像"
  # 容器内访问宿主机 API 需改写 loopback
  K6_BASE_URL=$(echo "$BASE_URL" | sed -E 's#//(localhost|127\.0\.0\.1)#//host.docker.internal#')
  K6_CMD=(docker run --rm -v "$PWD/eval:/eval" -w /eval grafana/k6:latest run)
else
  echo "[run_load_test] 错误:既无 k6 也无 docker,无法执行压测" >&2
  exit 2
fi

echo "[run_load_test] PROFILE=$PROFILE BASE_URL=$K6_BASE_URL"
# 注意:docker 模式下 results 目录经 -v 挂载回宿主,路径以 /eval 为根
if [ "${K6_CMD[0]}" = "docker" ]; then
  SUMMARY_IN_CONTAINER="/eval/results/loadtest_summary_${TS}.json"
else
  SUMMARY_IN_CONTAINER="$SUMMARY_JSON"
fi

"${K6_CMD[@]}" \
  -e BASE_URL="$K6_BASE_URL" \
  -e PROFILE="$PROFILE" \
  -e K6_SUMMARY_JSON="$SUMMARY_IN_CONTAINER" \
  ${LOADTEST_USER:+-e LOADTEST_USER="$LOADTEST_USER"} \
  ${LOADTEST_PASSWORD:+-e LOADTEST_PASSWORD="$LOADTEST_PASSWORD"} \
  load_test_k6.js
K6_EXIT=$?

if [ -f "$SUMMARY_JSON" ]; then
  python3 eval/render_load_report.py \
    --summary "$SUMMARY_JSON" \
    --profile "$PROFILE" \
    --base-url "$BASE_URL" \
    --k6-exit "$K6_EXIT" \
    --out "$REPORT_MD"
  echo "[run_load_test] 报告: $REPORT_MD"
else
  echo "[run_load_test] 警告:未生成 summary JSON,跳过报告渲染" >&2
fi

echo "[run_load_test] k6 退出码: $K6_EXIT (0=全部 thresholds 达标)"
exit $K6_EXIT
