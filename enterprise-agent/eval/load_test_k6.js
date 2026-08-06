// k6 阶梯压测脚本(load-test-and-dr-drill / tasks 1.2)
//
// 覆盖核心接口:
//   - GET  /health                (健康检查,无鉴权)
//   - POST /api/v1/chat/message   (对话接口,JWT 鉴权,完整工作流)
//
// 达标判定对齐 production-readiness SLA 初值:
//   核心接口 p95 ≤ 2s / p99 ≤ 5s / 错误率 < 0.5%,未达标 thresholds 失败 → 非零退出。
// 注意:SLA 口径对话类接口以「首 token」计;本脚本对 /chat/message 量的是完整响应时长,
// 属更严口径,报告中需注明。
//
// 运行(本机已装 k6):
//   k6 run -e BASE_URL=http://localhost:8000 eval/load_test_k6.js
// 冒烟档(缩短阶梯,验证脚本可用性):
//   k6 run -e PROFILE=smoke eval/load_test_k6.js
// Docker 兜底(本机无 k6):
//   docker run --rm -v "$PWD/eval:/eval" -w /eval grafana/k6:latest run \
//     -e BASE_URL=http://host.docker.internal:8000 load_test_k6.js
//
// 推荐经 eval/run_load_test.sh 执行(自动落盘 summary 到 eval/results/)。

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";
import { textSummary } from "https://jslib.k6.io/k6-summary/0.0.2/index.js";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const PASSWORD = __ENV.LOADTEST_PASSWORD || "ChangeMe123!";
// 多用户池:应用层限流为 30 req/min/用户(app/middleware/rate_limit.py),
// 单用户压测会打到限流而非容量——用种子用户池分摊(每用户独立 token)。
// 可用 LOADTEST_USERS="用户A,用户B" 覆盖;池大小应 ≥ 预估 chat 峰值 req/min ÷ 30。
const USER_POOL = (__ENV.LOADTEST_USERS ||
  "销售员张三,销售员王芳,销售员李雷,销售经理赵六,客服李四,客服韩梅梅,财务王五,财务经理钱八,HR孙九,管理员钱七"
).split(",");
const PROFILE = __ENV.PROFILE || "formal";

// 阶梯定义:formal 为正式压测;smoke 仅验证脚本链路可用
const STAGES = {
  formal: {
    health: [
      { duration: "1m", target: 50 },
      { duration: "2m", target: 50 },
      { duration: "1m", target: 100 },
      { duration: "2m", target: 100 },
      { duration: "1m", target: 200 },
      { duration: "2m", target: 200 },
      { duration: "30s", target: 0 },
    ],
    chat: [
      // 阶梯上限按应用层限流策略设计:30 req/min/用户 × 10 用户池 = 300 req/min。
      // 超过策略包线的压测测的是限流器(429),不是系统容量。
      // 真实对话耗时 1-15s,VU=10 时聚合约 60-100 req/min,留 3 倍余量。
      { duration: "1m", target: 4 },
      { duration: "2m", target: 4 },
      { duration: "1m", target: 7 },
      { duration: "2m", target: 7 },
      { duration: "1m", target: 10 },
      { duration: "2m", target: 10 },
      { duration: "30s", target: 0 },
    ],
  },
  smoke: {
    health: [
      { duration: "10s", target: 5 },
      { duration: "20s", target: 10 },
      { duration: "10s", target: 0 },
    ],
    chat: [
      { duration: "10s", target: 2 },
      { duration: "20s", target: 3 },
      { duration: "10s", target: 0 },
    ],
  },
};

const stages = STAGES[PROFILE] || STAGES.formal;

// 对话接口完整响应时长(独立 Trend,便于与 SLA 首 token 口径区分)
const chatLatency = new Trend("chat_message_duration", true);
// 429 限流占比(独立 Rate):限流是策略内流控,与系统故障(5xx)分开统计
const chatRateLimited = new Rate("chat_rate_limited");

export const options = {
  scenarios: {
    health: {
      executor: "ramping-vus",
      exec: "hitHealth",
      stages: stages.health,
      gracefulStop: "10s",
    },
    chat: {
      executor: "ramping-vus",
      exec: "hitChat",
      stages: stages.chat,
      gracefulStop: "30s",
    },
  },
  thresholds: {
    // 错误率(SLA < 0.5%),按接口分别判定
    "http_req_failed{endpoint:health}": ["rate<0.005"],
    "http_req_failed{endpoint:chat}": ["rate<0.005"],
    // 核心接口延迟(SLA p95 ≤ 2s / p99 ≤ 5s)
    "http_req_duration{endpoint:health}": ["p(95)<2000", "p(99)<5000"],
    "http_req_duration{endpoint:chat}": ["p(95)<2000", "p(99)<5000"],
  },
  // 单请求超时兜底:对话接口云端 LLM 慢时防止 VU 永久挂起
  noConnectionReuse: false,
  // summary 导出包含 p(99),供 render_load_report.py 出报告
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

// 登录用户池,token 按 VU 轮转分摊(压测对象是承载能力,非登录接口)
// 注意:/auth/login 自身有限流(10/min),429 时按 retry_after_seconds 退避重试
function loginWithRetry(username) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = http.post(
      `${BASE_URL}/api/v1/auth/login`,
      JSON.stringify({ username, password: PASSWORD }),
      { headers: { "Content-Type": "application/json" }, timeout: "30s" }
    );
    if (res.status === 200) {
      return res.json("access_token");
    }
    if (res.status === 429) {
      let wait = 62;
      try {
        wait = (res.json("retry_after_seconds") || 60) + 2;
      } catch (e) { /* 用默认等待 */ }
      console.log(`登录限流(${username}),${wait}s 后重试(${attempt + 1}/3)`);
      sleep(wait);
      continue;
    }
    throw new Error(`登录失败(${username}, ${res.status}): ${res.body} —— 检查 BASE_URL / LOADTEST_USERS`);
  }
  throw new Error(`登录失败(${username}): 多次限流重试后仍 429`);
}

export function setup() {
  const tokens = [];
  for (const username of USER_POOL) {
    tokens.push(loginWithRetry(username));
    sleep(1); // 控制登录节奏,少触发 10/min 限流
  }
  return { tokens };
}

const CHAT_PROMPTS = [
  "你好",
  "销售政策里退货怎么处理?",
  "帮我查一下常见问题FAQ",
  "产品手册里支持哪些部署方式?",
];

export function hitHealth() {
  const res = http.get(`${BASE_URL}/health`, {
    tags: { endpoint: "health" },
    timeout: "10s",
  });
  check(res, { "health 200": (r) => r.status === 200 });
  sleep(0.1);
}

export function hitChat(data) {
  const payload = JSON.stringify({
    message: CHAT_PROMPTS[Math.floor(Math.random() * CHAT_PROMPTS.length)],
  });
  // 随机取池内 token:多 scenario 下 VU 编号从全局池分配(实测 chat VU 编号稀疏),
  // 任何按编号取模的映射都会让多个 VU 挤同一用户触发 30/min 限流(第 5-7 轮实测教训);
  // 随机均匀分配下每用户期望速率 = 聚合/池大小,泊松分布越限概率可忽略
  const token = data.tokens[Math.floor(Math.random() * data.tokens.length)];
  const res = http.post(`${BASE_URL}/api/v1/chat/message`, payload, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    tags: { endpoint: "chat" },
    timeout: "120s",
  });
  chatLatency.add(res.timings.duration);
  chatRateLimited.add(res.status === 429);
  check(res, {
    "chat 200": (r) => r.status === 200,
    "chat 有回答": (r) => {
      try {
        return typeof r.json("answer") === "string";
      } catch (e) {
        return false;
      }
    },
  });
  // 思考时间:对话是交互式负载;无节奏时 429 快速失败会形成 VU 空转放大,
  // 聚合需求超出限流包线后进入"越限流越快"的恶性循环(第 1-3 轮实测教训)
  sleep(3 + Math.random() * 3);
}

export function handleSummary(data) {
  const out = { stdout: textSummary(data, { indent: " ", enableColors: false }) };
  if (__ENV.K6_SUMMARY_JSON) {
    out[__ENV.K6_SUMMARY_JSON] = JSON.stringify(data, null, 2);
  }
  return out;
}
