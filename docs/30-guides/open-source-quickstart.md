# Open-source quickstart / 开源快速开始

## Current milestone / 当前阶段

Stage one targets reproducible isolated startup with synthetic examples and honest capability and source-rights boundaries. It is not a claim of real enterprise deployment, formal UAT, or production readiness.

第一阶段目标是隔离启动、合成示例与清楚的能力和来源边界，不代表真实企业部署、正式 UAT 或生产就绪。

## Starter verification / 启动入口核验

Scoped macOS arm64 checks passed with Python 3.13.15 and a previously approved binary-driver
test adapter. Run-05 passed 15 real HTTP checks and 14 focused demo tests after a startup-log correction; owned services were stopped with data retained. Run-04 browser checks passed login, both greeting shortcuts, unsupported-operation rejection, current-session history, refresh/login isolation, relogin and logout. The log-only follow-up did not change UI bytes. This is not native libpq proof: the final precommit offline checks passed, while Linux CI and clean committed binding remain pending; stage one is not complete.

From the repository root, with prerequisites satisfied in an isolated Python environment:

    python -I -B enterprise-agent/scripts/run_synthetic_demo.py plan

The plan performs no startup. Choose a new nonexistent, non-symlink run directory:

    python -I -B enterprise-agent/scripts/run_synthetic_demo.py start --execute --run-dir enterprise-agent/eval/results/my-synthetic-demo-01

Startup prints a loopback URL and random test credentials. Keep this output private.
Open the printed URL locally, sign in and send “你好” or “您好”. Replies are fixed synthetic
greetings, not model answers. Only login, greetings and own history are supported; RAG,
approvals and business operations are rejected. A demo marker distinguishes this profile.

Optional tracked acceptance (creates synthetic users/sessions and a redacted report):

    python -I -B enterprise-agent/scripts/check_synthetic_demo.py --execute --require-python-driver --run-dir enterprise-agent/eval/results/my-synthetic-demo-01

The pure-driver option deliberately rejects binary/C implementations, including the
historical Mac test adapter. Final native-driver execution remains pending.

Stop after use, or after partial startup with a retained receipt:

    python -I -B enterprise-agent/scripts/run_synthetic_demo.py stop --execute --run-dir enterprise-agent/eval/results/my-synthetic-demo-01

Stop targets owned services and retains containers, volumes and evidence; no deletion.
Use another fresh directory for another start. Keep private-state.json, logs and credentials
out of commits/public uploads. Share only inspected redacted acceptance reports.
Loopback bindings and Python guards are not OS/container-wide network isolation.

## Prerequisites under verification / 正在核验的前置条件

The planned starter uses Python 3.11 or later, the existing production Python dependencies,
Docker for isolated PostgreSQL/Redis, and native **libpq** on the host. The project's pure
psycopg package needs libpq available to the operating system's dynamic loader; pip
installation alone is insufficient. No new psycopg binary dependency is added for the
demo. For Debian/Ubuntu, the system runtime package is libpq5. In an isolated environment with package-install permission, install it before the Python requirements. The dedicated Linux CI now specifies this prerequisite, but its actual result is still pending.

计划入口需要 Python 3.11+、现有生产依赖、运行隔离 PostgreSQL/Redis 的 Docker，以及
宿主机原生 libpq。仅安装 Python requirements 不代表环境已经完整可用；本演示不会另加
psycopg 二进制依赖。Debian/Ubuntu 对应系统包为 libpq5；Linux CI 已明确安装此前置，但尚待真实运行结果。

The approved narrow profile uses the real application core but synthetic greeting responses.
It is not a generic replacement API and does not demonstrate real RAG or business actions.
Production mode must refuse the profile. A minimal Debian/Ubuntu setup sequence (requires system package-install permission; Linux execution evidence pending) is:

    sudo apt-get update
    sudo apt-get install -y --no-install-recommends libpq5
    python3 -m venv .venv-demo
    . .venv-demo/bin/activate
    python -m pip install -r enterprise-agent/deploy/requirements-prod.txt
    python -I -B -c "import importlib.util as u; import psycopg; assert u.find_spec('psycopg_binary') is None; assert u.find_spec('psycopg_c') is None; assert psycopg.pq.__impl__ == 'python'; print(psycopg.pq.version())"

Use a new environment directory; Docker must already be running and accessible. This adds no new Python dependency. Do not install a binary extra merely to bypass the native-driver acceptance check.

## Capability boundaries / 能力边界

| Area | What is established | What is not established |
| --- | --- | --- |
| Approval controls | Decision and requester execution confirmation are separate; failed/unknown actions retain human holds | Real enterprise approval acceptance or automatic hold release |
| Offline checks | Candidate-bound unit, integrity and synthetic contract evidence | Real model answers, complete RAG, business-user acceptance |
| History | Backend persistence and session-specific queries; current-session UI history checked | Refresh returns to login; relogin starts a new empty session, with no visible old-session recovery entry or complete history manager |
| Synthetic examples | Disposable test identities and business fixtures | Real employee or customer outcomes |
| Demo providers | Must be labeled individually by the starter's actual implementation | Real CRM/mail/ticket effects from a substitute API |
| Licenses and assets | Root project license and separate provenance inventory exist | Blanket clearance of unknown third-party material |

A full page refresh returns to login. After relogin there is no visible entry to recover the old session. Current-session history may show a persisted snapshot with unknown status; that is not a successful business execution receipt. Do not claim automatic cross-refresh recovery.

The source inventory now contains 465 records: the historical 457 baseline plus eight new engineering fixtures. Registration does not clear unknown rights. The maintainer stated that three C17 documents (two departmental documents and after-sales policy) and eight CRM examples were fictional from creation; this is scoped author testimony, not external permission or clearance of other C17 material. The completed separate CRM increment labels eight fictional customers and uses NOT-A-PHONE telephone placeholders and example.invalid customer email addresses. The internal-mail seed deliberately retains fictional-demo-manager@company.internal with a synthetic-data comment: this private demo domain is required by the unchanged internal-mail safety classifier. It is not a customer address or a relaxed mail policy. Three focused tests passed; order and non-contact fields were unchanged. The expected full Python count is 2137 (2120 baseline + 14 demo + 3 CRM). Final precommit offline tests passed; clean committed binding and Linux CI remain pending.

The final candidate identity and Linux result must be added after verification. Existing successful CI evidence does not by itself prove a new starter works. See [source provenance](../50-engineering/license-provenance.md) and [third-party notices](../../THIRD_PARTY_NOTICES.md); unknown rights are not permission to redistribute.

## Later stages / 后续三个阶段

1. **Enterprise pilot evaluation / 企业试点评估**: choose one concrete team problem, assess data permission and integration feasibility, and agree on measurable success criteria. Start with read-only knowledge questions and access isolation; do not require a full organization before evaluating value.
2. **Real-environment pilot / 真实环境试点**: use an agreed independent environment and approved business sandboxes. A small number of real users and a business contact judge actual results. Expand from read-only questions to a limited integration only after evidence supports it. Synthetic role tests remain technical preparation, not formal business acceptance.
3. **Production use / 生产使用**: separately establish security/privacy review, operational ownership, backups and recovery, monitoring, incident handling, upgrade rollback and staged rollout. A merge does not authorize deployment.

## Merge boundary / 合并边界

Stage-one merge requires verified reproducibility, accurate limitations, resolved material distribution-rights blockers and current candidate checks. Later enterprise milestones remain openly unfinished. Do not replace missing evidence with a PASS label.

Retained historical screenshots were not replaced and may still display historical contact details or additional unconfirmed recipients. The text/fixture update is not a claim that all visual examples or their source rights have been cleared.
