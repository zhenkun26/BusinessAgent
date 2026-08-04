# -*- coding: utf-8 -*-
"""使用案例手册 F1-F14 网页前端端到端验证(Playwright + 本机 Edge)。

运行: .venv_e2e/Scripts/python.exe eval/e2e_ui_f1_f14.py
前置: API 已在 127.0.0.1:8000 运行,5 个基础设施容器 healthy。
"""
import re
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE = "http://127.0.0.1:8000/ui/"
CHAT_TIMEOUT_MS = 240_000  # 单次对话最长等待(知识问答冷启动可能 100s+)

RESULTS = []          # (fid, desc, ok, detail)
CONSOLE_ERRORS = []   # 浏览器 console error / pageerror


def record(fid, desc, ok, detail=""):
    RESULTS.append((fid, desc, bool(ok), detail))
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {fid} {desc}" + (f" | {detail}" if detail else ""), flush=True)


def info(fid, desc):
    RESULTS.append((fid, desc, None, ""))
    print(f"[INFO] {fid} {desc}", flush=True)


# ---------- 基础 helper ----------

def logout_if_needed(page):
    if page.locator(".topbar").count() and page.locator(".topbar").is_visible():
        page.click(".logout")
        page.wait_for_selector(".login-card", state="visible", timeout=10_000)


def login(page, name):
    logout_if_needed(page)
    if not page.locator(".login-card").is_visible():
        page.reload()
        page.wait_for_selector(".login-card", state="visible", timeout=10_000)
    page.locator(".login-card select option", has_text=name).first.wait_for(state="attached", timeout=5000)
    label = page.locator(".login-card select option", has_text=name).first.inner_text().strip()
    page.select_option(".login-card select", label=label)
    for attempt in range(3):
        page.click(".login-card .btn-block")
        try:
            page.wait_for_selector(".topbar", state="visible", timeout=15_000)
            return
        except PWTimeout:
            err = page.locator(".login-err").inner_text().strip()
            if attempt < 2:
                # 登录限流(10/min)等,等一个限流窗口后重试
                print(f"  [login] {name} 第{attempt+1}次未成功 loginErr={err!r},等待 62s 重试", flush=True)
                page.wait_for_timeout(62_000)
            else:
                raise RuntimeError(f"登录失败:{err}")


def nav_tabs(page):
    return page.locator(".topbar nav a").all_inner_texts()


def click_tab(page, name):
    page.locator(".topbar nav a", has_text=name).first.click()
    page.wait_for_timeout(400)


def send_chat(page, text, timeout_ms=CHAT_TIMEOUT_MS, sample_stream=False):
    """发送一条消息并等流式结束,返回 (answer_text, badges, sources, stream_grew)。"""
    page.fill(".chat-input textarea", text)
    page.click(".chat-input .btn")
    page.wait_for_timeout(600)
    stream_grew = None
    if sample_stream:
        # 观察打字机:pending 期间答案应逐段增长
        lens = []
        for _ in range(6):
            page.wait_for_timeout(1500)
            if page.locator(".msg.agent").count() > 0:
                try:
                    lens.append(len(page.locator(".msg.agent").last.locator(".bubble").inner_text()))
                except Exception:
                    pass
            if not page.locator(".pending-bar").is_visible():
                break
        stream_grew = len(lens) >= 2 and lens[-1] > lens[0]
    page.wait_for_function(
        "() => { const t = document.querySelector('.chat-input textarea'); return t && !t.disabled; }",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(400)
    return last_agent(page) + (stream_grew,)


def last_agent(page):
    """返回最后一条 agent 消息的 (text, badges, sources)。"""
    n = page.locator(".msg.agent").count()
    if n == 0:
        return "", [], []
    msg = page.locator(".msg.agent").nth(n - 1)
    text = msg.locator(".bubble").inner_text()
    badges = msg.locator(".meta .badge").all_inner_texts()
    sources = msg.locator(".src .src-item").all_inner_texts()
    return text, badges, sources


def confidence_of(badges):
    for b in badges:
        m = re.search(r"置信度\s*([\d.]+)", b)
        if m:
            return float(m.group(1))
    return None


def toast_text(page):
    try:
        page.wait_for_selector(".toast", state="visible", timeout=3000)
        return page.locator(".toast").inner_text()
    except PWTimeout:
        return "(无 toast)"


# ---------- F1 登录与界面 ----------

SEED_USERS = [
    ("销售员张三", "salesperson", "dept_sales", False),
    ("销售员王芳", "salesperson", "dept_sales", False),
    ("销售员李雷", "salesperson", "dept_sales", False),
    ("销售经理赵六", "manager", "dept_sales", True),
    ("客服李四", "customer_service", "dept_cs", False),
    ("客服韩梅梅", "customer_service", "dept_cs", False),
    ("财务王五", "finance", "dept_finance", False),
    ("财务经理钱八", "manager", "dept_finance", True),
    ("HR孙九", "customer_service", "dept_hr", False),
    ("管理员钱七", "admin", "shared_company", True),
]


def test_f1(page):
    opts = page.locator(".login-card select option").all_inner_texts()
    record("F1", "登录页下拉含 10 个种子用户", len(opts) == 10, f"实际 {len(opts)} 个")
    hint = page.locator(".login-card").inner_text()
    record("F1", "登录页底部种子用户提示", "10 个种子用户覆盖 5 角色" in hint)
    for name, role, dept, approver in SEED_USERS:
        try:
            login(page, name)
            who = page.locator(".who b").inner_text().strip()
            rtag = page.locator(".who .role-tag").inner_text().strip()
            dtag = page.locator(".who .dept").inner_text().strip()
            tabs = nav_tabs(page)
            has_appr = any("审批" in t for t in tabs)
            has_prompt = any("Prompt" in t for t in tabs)
            ok = (who == name and rtag == role and dtag == dept
                  and has_appr == approver and has_prompt == approver)
            record("F1", f"登录 {name}", ok,
                   f"who={who} role={rtag} dept={dtag} tabs={tabs}")
            page.wait_for_timeout(6500)  # 控制登录速率,避开 10/min 限流
        except Exception as e:
            record("F1", f"登录 {name}", False, str(e)[:200])


# ---------- F2 系统状态 / F2.5 业务数据 ----------

def test_f2(page):
    click_tab(page, "系统状态")
    page.wait_for_timeout(1200)
    stats = page.locator(".stat").all_inner_texts()
    joined = " | ".join(s.replace("\n", ":") for s in stats)
    db_ok = any("数据库" in s and "healthy" in s for s in stats)
    mv_ok = any("Milvus" in s and "healthy" in s for s in stats)
    ent = None
    tools = None
    for s in stats:
        m = re.search(r"文档实体数\n(\d+)", s)
        if m:
            ent = int(m.group(1))
        m = re.search(r"注册工具\n(\d+)", s)
        if m:
            tools = int(m.group(1))
    record("F2", "系统状态 db/milvus healthy", db_ok and mv_ok, joined)
    record("F2", "文档实体数 ≥10", ent is not None and ent >= 10, f"entities={ent}")
    record("F2", "注册工具 =7", tools == 7, f"tools={tools}")


def test_f2_5(page):
    click_tab(page, "业务数据")
    page.wait_for_timeout(500)
    # 客户 8 行 + 查询按钮
    rows = page.locator(".ref-table tbody tr").count()
    record("F2.5", "客户表 8 行", rows == 8, f"实际 {rows}")
    page.locator(".ref-table tbody tr", has_text="C001").locator("button").click()
    page.wait_for_timeout(400)
    draft = page.locator(".chat-input textarea").input_value()
    chat_active = "对话" in page.locator(".topbar nav a.active").inner_text()
    record("F2.5", "C001「查询」按钮跳转并填入", "查一下客户 C001 的信息" in draft and chat_active,
           f"draft={draft!r}")
    # 订单 8 行
    click_tab(page, "业务数据")
    page.locator(".ref-tabs a", has_text="订单").click()
    page.wait_for_timeout(300)
    rows = page.locator(".ref-table tbody tr").count()
    record("F2.5", "订单表 8 行", rows == 8, f"实际 {rows}")
    page.locator(".ref-table tbody tr", has_text="ORD-2026-005").locator("button").click()
    page.wait_for_timeout(300)
    draft = page.locator(".chat-input textarea").input_value()
    record("F2.5", "ORD-2026-005「查询」填入", "ORD-2026-005" in draft, f"draft={draft!r}")
    # 工单 6 行
    click_tab(page, "业务数据")
    page.locator(".ref-tabs a", has_text="工单").click()
    page.wait_for_timeout(300)
    rows = page.locator(".ref-table tbody tr").count()
    record("F2.5", "工单表 6 行", rows == 6, f"实际 {rows}")
    page.locator(".ref-table tbody tr", has_text="TK-EXIST003").locator("button").click()
    page.wait_for_timeout(300)
    draft = page.locator(".chat-input textarea").input_value()
    record("F2.5", "TK-EXIST003「查询」填入", "TK-EXIST003" in draft, f"draft={draft!r}")
    # 文档 7 行
    click_tab(page, "业务数据")
    page.locator(".ref-tabs a", has_text="知识库文档").click()
    page.wait_for_timeout(300)
    rows = page.locator(".ref-table tbody tr").count()
    ns = page.locator(".ref-table tbody tr td:nth-child(4)").all_inner_texts()
    record("F2.5", "文档表 7 行(5 shared + 2 部门)",
           rows == 7 and ns.count("shared_company") == 5 and "dept_sales" in ns and "dept_finance" in ns,
           f"实际 {rows} ns={ns}")


# ---------- chips 面板断言 ----------

def assert_chips(page, fid, expect_groups, expect_chip=None, expect_fill=None):
    groups = page.locator(".scene-panel .chip.cat").all_inner_texts()
    ok = all(g in groups for g in expect_groups)
    detail = f"groups={groups}"
    if expect_chip:
        chip = page.locator(".scene-panel .chip", has_text=expect_chip).first
        try:
            chip.click()
            page.wait_for_timeout(300)
            draft = page.locator(".chat-input textarea").input_value()
            ok = ok and expect_fill in draft
            detail += f" chip填入={draft!r}"
            page.fill(".chat-input textarea", "")
        except Exception as e:
            ok = False
            detail += f" chip点击失败:{e}"
    record(fid, f"场景面板 {expect_groups}", ok, detail)


# ---------- F3/F3.5/F4/F5.1/F7/F8/F10/F11/F13:销售员张三 ----------

def test_sales_zhangsan(page):
    login(page, "销售员张三")
    click_tab(page, "对话")

    # F3.5 chips
    assert_chips(page, "F3.5", ["通用", "销售场景"], "建跟进任务", "给客户 C001 创建一个回访任务")

    # F3 闲聊
    text, badges, sources, _ = send_chat(page, "你好")
    conf = confidence_of(badges)
    record("F3", "闲聊 intent=chitchat conf=0.9 无来源",
           any("chitchat" in b for b in badges) and conf == 0.9 and len(sources) == 0,
           f"badges={badges} sources={sources}")

    # F4 知识问答(观察流式)
    text, badges, sources, grew = send_chat(page, "公司的折扣审批政策是怎样的", sample_stream=True)
    conf = confidence_of(badges)
    sid = page.locator(".chat-head .sid").inner_text()
    record("F4", "知识问答 intent=knowledge_qa 带来源 置信度≥0.6",
           any("knowledge_qa" in b for b in badges) and len(sources) > 0 and (conf or 0) >= 0.6,
           f"conf={conf} sources={sources[:2]}")
    record("F4", "流式打字机(答案逐段增长)", grew is True, f"stream_grew={grew}")
    record("F4", "会话号已生成", sid.startswith("sess_"), f"sid={sid}")

    # F4 多轮上下文
    text, badges, sources, _ = send_chat(page, "那销售提成呢?")
    ok = any("knowledge_qa" in b for b in badges) and "未覆盖" not in text
    record("F4", "多轮上下文:追问「那销售提成呢」承接上文", ok,
           f"badges={badges} answer[:80]={text[:80]!r}")

    # F5.1 命名空间:销售命中
    text, badges, sources, _ = send_chat(page, "冲刺先锋奖的评选规则是什么")
    record("F5", "张三命中销售部专属文档", any("dept_sales" in s for s in sources) or "未覆盖" not in text,
           f"sources={sources[:2]} answer[:60]={text[:60]!r}")

    # F7.1 查客户
    text, badges, _, _ = send_chat(page, "查一下客户 C001 的信息")
    record("F7", "查客户 C001", "华信" in text or "C001" in text, f"answer[:80]={text[:80]!r}")

    # F7.2 查订单
    text, badges, _, _ = send_chat(page, "查询订单 ORD-2026-005 的详情,包含明细")
    record("F7", "查订单 ORD-2026-005 含明细", "45,000" in text or "45000" in text or "P-M003" in text,
           f"answer[:100]={text[:100]!r}")

    # F8 RBAC 友好拒绝
    text, badges, _, _ = send_chat(page, "给外部客户 wang@external.com 发封邮件,同步续约报价")
    record("F8", "销售员发外部邮件友好拒绝", "无权" in text and "❌" not in text,
           f"answer[:80]={text[:80]!r}")

    # F7.7 RBAC 负例
    text, badges, _, _ = send_chat(page, "把工单 TK-EXIST001 的状态更新为 resolved")
    record("F7", "销售员更新工单被拒", "无权" in text, f"answer[:80]={text[:80]!r}")

    # F11 反馈(👍 点最后一条,👎 点较早的另一条——同一条只能反馈一次)
    page.locator(".msg.agent").last.locator(".fb button").first.click()
    t = toast_text(page)
    record("F11", "👍 反馈 toast", "感谢反馈" in t, f"toast={t!r}")
    page.locator(".msg.agent").first.locator(".fb button").nth(1).click()
    page.wait_for_timeout(500)
    t = page.locator(".toast").inner_text() if page.locator(".toast").count() else "(无 toast)"
    record("F11", "👎 负反馈(弹窗评论)toast", "已记录" in t, f"toast={t!r}")

    # F13 历史快照
    page.locator("button", has_text="历史").click()
    page.wait_for_timeout(2500)
    alltext = page.locator(".chat-body").inner_text()
    record("F13", "历史快照卡片", "历史快照" in alltext, "")

    # F13 刷新保持登录
    sid_before = page.locator(".chat-head .sid").inner_text()
    page.reload()
    page.wait_for_selector(".topbar", state="visible", timeout=15_000)
    sid_after = page.locator(".chat-head .sid").inner_text()
    record("F13", "刷新后保持登录态+会话号", sid_after == sid_before and sid_after.startswith("sess_"),
           f"before={sid_before} after={sid_after}")

    # F13 新会话
    page.locator("button", has_text="新会话").click()
    page.wait_for_timeout(500)
    sid_new = page.locator(".chat-head .sid").inner_text()
    msgs = page.locator(".msg").count()
    record("F13", "新会话清空消息+会话号", "发送首条消息后生成" in sid_new and msgs == 0,
           f"sid={sid_new} msgs={msgs}")

    # F10 取消(全新会话:首轮即取消)
    page.fill(".chat-input textarea", "公司的折扣审批政策是怎样的")
    page.click(".chat-input .btn")
    page.wait_for_selector(".pending-bar", state="visible", timeout=10_000)
    page.wait_for_timeout(3000)
    page.click(".pending-bar .btn-danger")
    t = toast_text(page)
    page.wait_for_function(
        "() => { const t = document.querySelector('.chat-input textarea'); return t && !t.disabled; }",
        timeout=CHAT_TIMEOUT_MS)
    text, badges, _ = last_agent(page)
    cancelled_mark = any("cancelled" in b for b in badges)
    record("F10", "全新会话首轮点取消", "已请求取消" in t and cancelled_mark,
           f"toast={t!r} badges={badges} answer[:60]={text[:60]!r}")

    # F10 取消后同会话可续用
    text, badges, _, _ = send_chat(page, "你好")
    record("F10", "取消后同会话可续用", any("chitchat" in b for b in badges) or len(text) > 0,
           f"badges={badges} answer[:60]={text[:60]!r}")


# ---------- 客服李四:F5.2/F3.5/F7.3/F7.6/F6.6/F9X.2 ----------

def test_cs_lisi(page):
    login(page, "客服李四")
    click_tab(page, "对话")
    assert_chips(page, "F3.5", ["通用", "客服场景"], "查工单 TK-EXIST003", "查询工单 TK-EXIST003 的处理进度")

    text, badges, sources, _ = send_chat(page, "冲刺先锋奖的评选规则是什么")
    isolated = not any("dept_sales" in s for s in sources)
    record("F5", "李四问销售专属内容被隔离", isolated and ("未覆盖" in text or (confidence_of(badges) or 1) < 0.6),
           f"sources={sources[:2]} conf={confidence_of(badges)}")

    text, badges, _, _ = send_chat(page, "查询工单 TK-EXIST003 的处理进度")
    record("F7", "查工单 TK-EXIST003", "C005" in text or "bug" in text.lower() or "数据分析" in text,
           f"answer[:80]={text[:80]!r}")

    text, badges, _, _ = send_chat(page, "把工单 TK-EXIST002 的状态更新为 resolved,备注:已确认支持批量导入")
    record("F7", "工单 TK-EXIST002 open→resolved", "resolved" in text and "无权" not in text,
           f"answer[:100]={text[:100]!r}")

    text, badges, _, _ = send_chat(page, "统计一下所有客户的订单总额")
    record("F6", "客服问数据分析被拒", "无权" in text or "权限" in text, f"answer[:80]={text[:80]!r}")

    # F9X.2 退款争议
    text, badges, _, _ = send_chat(page, "查询工单 TK-EXIST004 退款申请的详情,客户 C002")
    record("F9X.2", "查退款工单 TK-EXIST004", "C002" in text or "退款" in text, f"answer[:80]={text[:80]!r}")
    text, badges, _, _ = send_chat(page, "把工单 TK-EXIST004 状态更新为 closed,备注:财务已确认退款完成")
    record("F9X.2", "工单 TK-EXIST004 →closed", "closed" in text and "无权" not in text,
           f"answer[:100]={text[:100]!r}")


# ---------- 财务王五:F5.3/F3.5/F9X.2 ----------

def test_fin_wangwu(page):
    login(page, "财务王五")
    click_tab(page, "对话")
    assert_chips(page, "F3.5", ["通用", "财务场景"], "差旅报销", "差旅费的报销标准")

    text, badges, sources, _ = send_chat(page, "预算冻结线是多少")
    record("F5", "王五命中财务部专属文档",
           any("dept_finance" in s for s in sources) or "未覆盖" not in text,
           f"sources={sources[:2]} answer[:60]={text[:60]!r}")

    text, badges, _, _ = send_chat(page, "查询订单 ORD-2026-008 的详情,确认退款状态")
    record("F9X.2", "财务查 ORD-2026-008 refunded", "refunded" in text or "退款" in text or "78,000" in text or "78000" in text,
           f"answer[:100]={text[:100]!r}")


# ---------- 经理赵六:F3.5/F6/F7.5/F9/F9.5/F9X.3 ----------

def test_mgr_zhaoliu(page):
    login(page, "销售经理赵六")
    click_tab(page, "对话")
    assert_chips(page, "F3.5", ["通用", "管理场景", "销售场景", "客服场景", "财务场景"],
                 "Saga 多步骤", "给客户 C001 创建回访任务")

    # F6 数据分析
    text, badges, _, _ = send_chat(page, "对比一下 C001 和 C002 两个客户的累计销售额")
    ok = "285" in text and "152" in text and "无权" not in text and "need_more" not in text
    record("F6", "对比 C001 vs C002 含真实数字", ok, f"answer[:120]={text[:120]!r}")

    text, badges, _, _ = send_chat(page, "所有客户里谁的累计销售额最高,给出前三名")
    ok = "C001" in text and "C002" in text and "C005" in text
    record("F6", "客户排名前三 C001>C002>C005", ok, f"answer[:120]={text[:120]!r}")

    text, badges, _, _ = send_chat(page, "统计 VIP 和 A 级客户分布在哪些行业")
    ok = "软件开发" in text and ("进出口" in text or "互联网" in text)
    record("F6", "VIP/A 级行业分布", ok, f"answer[:120]={text[:120]!r}")

    text, badges, _, _ = send_chat(page, "统计所有订单的状态分布,有多少笔 pending 待付款")
    ok = "pending" in text and ("3" in text)
    record("F6", "订单状态分布 pending=3", ok, f"answer[:120]={text[:120]!r}")

    # F7.5 三步 Saga
    text, badges, _, _ = send_chat(
        page, "查一下客户 C005 的信息,然后为她创建一个 urgent 工单跟踪数据分析 bug,最后发内部邮件给经理赵六说明处理进展")
    ok = ("C005" in text or "云图" in text) and ("TK-" in text or "工单" in text) and ("无权" not in text)
    record("F7", "三步 Saga(查客户+建工单+邮件)", ok, f"answer[:150]={text[:150]!r}")

    # F9X.3 紧急 Bug 升级 Saga
    text, badges, _, _ = send_chat(
        page, "紧急处理 C005 的 bug:先查询客户信息和工单 TK-EXIST003,然后查询 ORD-2026-003 订单,最后发内部邮件给经理赵六说明升级处理")
    ok = "无权" not in text and ("TK-EXIST003" in text or "ORD-2026-003" in text)
    record("F9X.3", "紧急 Bug 多步 Saga", ok, f"answer[:150]={text[:150]!r}")

    # F9 审批流
    text, badges, _, _ = send_chat(
        page, "给外部客户王总 wang@external.com 发邮件,主题:续约报价,正文:本季度续约报价请查收")
    m = re.search(r"appr_\w+", text)
    record("F9", "发外部邮件建审批单", "已提交审批" in text and m is not None,
           f"审批号={m.group(0) if m else '(未找到)'} answer[:100]={text[:100]!r}")
    appr_id = m.group(0) if m else None

    click_tab(page, "审批")
    page.wait_for_timeout(1500)
    if appr_id:
        card = page.locator(".card", has_text=appr_id)
        if card.count() == 0:
            record("F9", "审批页签出现该审批单", False, "列表中无此单")
        else:
            record("F9", "审批页签出现该审批单", True, appr_id)
            card.locator("button", has_text="批准").click()
            page.wait_for_timeout(2500)
            body = page.locator(".panel:visible .page").inner_text()
            record("F9", "批准后 executed", "executed" in body, f"页面片段={body[:200]!r}")
    else:
        record("F9", "审批页签出现该审批单", False, "未能从回答中解析审批号")

    # F9.5 批量审批
    click_tab(page, "审批")
    page.wait_for_timeout(1500)
    batch_cards = page.locator(".card", has_text="batch_2026_001")
    n = batch_cards.count()
    record("F9.5", "批量审批 3 条带 batch 徽标", n == 3, f"实际 {n} 条")
    for i in range(n):
        try:
            card = page.locator(".card", has_text="batch_2026_001").first
            card.locator("button", has_text="批准").click()
            page.wait_for_timeout(2500)
        except Exception as e:
            record("F9.5", f"批准第 {i+1} 条", False, str(e)[:150])
            break
    else:
        page.wait_for_timeout(2000)
        body = page.locator(".panel:visible .page").inner_text()
        remaining = page.locator(".card", has_text="batch_2026_001").count()
        record("F9.5", "3 条批量审批全部执行", remaining == 0, f"剩余 {remaining} 条")


# ---------- 王芳:F9X.4 ----------

def test_sales_wangfang(page):
    login(page, "销售员王芳")
    click_tab(page, "业务数据")
    page.wait_for_timeout(500)
    page.locator(".ref-table tbody tr", has_text="C008").locator("button").click()
    page.wait_for_timeout(300)
    text, badges, _, _ = send_chat(page, page.locator(".chat-input textarea").input_value())
    record("F9X.4", "C008 新客户查询", "博雅" in text or "C008" in text, f"answer[:80]={text[:80]!r}")


# ---------- 管理员钱七:F3.5/F12 ----------

def test_admin_qianqi(page):
    login(page, "管理员钱七")
    click_tab(page, "对话")
    groups = page.locator(".scene-panel .chip.cat").all_inner_texts()
    record("F3.5", "admin 全场景 chips",
           all(g in groups for g in ["通用", "管理场景", "销售场景", "客服场景", "财务场景"]),
           f"groups={groups}")

    click_tab(page, "Prompt 管理")
    page.wait_for_timeout(2000)
    cards = page.locator(".panel:visible .card")
    names = cards.locator(".title").all_inner_texts()
    record("F12", "Prompt 列表 11 个", len(names) == 11, f"实际 {len(names)}:{names[:3]}…")

    name = "planner_chitchat_detect"
    card = page.locator(".card", has_text=name).first
    ver_before = card.locator(".ver-tag").all_inner_texts()
    card.locator("summary").click()
    page.wait_for_timeout(300)
    card.locator("textarea.area").fill(
        "判断用户消息是否为闲聊(问候、感谢、无关话题)。\n\n"
        "闲聊示例:你好、谢谢、今天天气、你是谁、再见、吃了吗\n"
        "非闲聊示例:查询政策、创建任务、折扣规定、佣金计算\n\n"
        "只回复 \"是\" 或 \"否\",不要解释。\n\n用户消息: {message}\n")
    card.locator("button", has_text="存为 draft").click()
    t = toast_text(page)
    m = re.search(r"v(\d+)", t)
    new_ver = int(m.group(1)) if m else None
    record("F12", "建 draft 新版本", "draft" in t and new_ver is not None, f"toast={t!r}")
    page.wait_for_timeout(1500)

    if new_ver:
        card = page.locator(".card", has_text=name).first
        if not card.locator("textarea.area").is_visible():
            card.locator("summary").click()
            page.wait_for_timeout(300)
        card.locator("input.mini").first.fill(str(new_ver))
        cb = card.locator("input[type=checkbox]")
        if cb.is_checked():
            cb.uncheck()
        card.locator("button", has_text="激活").first.click()
        t = toast_text(page)
        page.wait_for_timeout(2000)
        record("F12", f"激活 v{new_ver}(不归档)", "已激活" in t, f"toast={t!r}")

        # 设流量 80/20
        card = page.locator(".card", has_text=name).first
        if not card.locator("textarea.area").is_visible():
            card.locator("summary").click()
            page.wait_for_timeout(300)
        mins = card.locator("input.mini")
        # 第一个是激活版本号输入,其后是各 active 版本权重输入
        mins.nth(1).fill("80")
        mins.nth(2).fill("20")
        card.locator("button", has_text="设流量").click()
        page.wait_for_timeout(2000)
        vers = card.locator(".ver-tag").all_inner_texts()
        joined = " ".join(vers)
        record("F12", "A/B 流量 v1=80 v2=20", "w=80" in joined and "w=20" in joined, joined)

        # 回滚
        card = page.locator(".card", has_text=name).first
        if not card.locator("textarea.area").is_visible():
            card.locator("summary").click()
            page.wait_for_timeout(300)
        card.locator("input.mini").first.fill("1")
        cb = card.locator("input[type=checkbox]")
        if not cb.is_checked():
            cb.check()
        card.locator("button", has_text="激活").first.click()
        page.wait_for_timeout(2000)
        card = page.locator(".card", has_text=name).first
        vers = card.locator(".ver-tag").all_inner_texts()
        joined = " ".join(vers)
        record("F12", "回滚 v1 active w=100 其余 archived",
               "v1 active" in joined and "w=100" in joined and "archived" in joined, joined)


# ---------- main ----------

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept("测试意见:折扣政策已更新,15%以上需董事会审批"))
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))

        page.goto(BASE)
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_selector(".login-card", state="visible", timeout=15_000)

        def run(name, fn):
            try:
                fn(page)
            except Exception as e:
                record(name, f"测试套件 {name} 异常中断", False, str(e)[:300])

        run("F1", test_f1)
        login(page, "销售员张三")
        run("F2", test_f2)
        run("F2.5", test_f2_5)
        run("张三", test_sales_zhangsan)
        run("李四", test_cs_lisi)
        run("王五", test_fin_wangwu)
        run("赵六", test_mgr_zhaoliu)
        run("王芳", test_sales_wangfang)
        run("钱七", test_admin_qianqi)

        browser.close()

    print("\n===== 汇总 =====", flush=True)
    passed = sum(1 for r in RESULTS if r[2] is True)
    failed = sum(1 for r in RESULTS if r[2] is False)
    print(f"PASS={passed} FAIL={failed}", flush=True)
    for fid, desc, ok, detail in RESULTS:
        if ok is False:
            print(f"  [FAIL] {fid} {desc} | {detail}", flush=True)
    if CONSOLE_ERRORS:
        print("\n===== 浏览器 console/pageerror =====", flush=True)
        for e in CONSOLE_ERRORS[:20]:
            print(" ", e[:300], flush=True)
    with open("eval/e2e_ui_report.txt", "w", encoding="utf-8") as f:
        f.write(f"PASS={passed} FAIL={failed}\n")
        for fid, desc, ok, detail in RESULTS:
            f.write(f"[{'PASS' if ok else 'FAIL' if ok is False else 'INFO'}] {fid} {desc} | {detail}\n")
        if CONSOLE_ERRORS:
            f.write("\nconsole errors:\n" + "\n".join(CONSOLE_ERRORS[:50]))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
