# -*- coding: utf-8 -*-
"""首轮 e2e 的补测:F10 取消、F11 👎、F9X.1、F9/F9.5 审批执行、F12 列表数。
复用 e2e_ui_f1_f14 的 helper;从 enterprise-agent 目录运行。"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "eval"))
from playwright.sync_api import sync_playwright

import e2e_ui_f1_f14 as base
from e2e_ui_f1_f14 import (
    BASE, CHAT_TIMEOUT_MS, CONSOLE_ERRORS, RESULTS,
    click_tab, last_agent, login, record, send_chat, toast_text,
)


def wait_idle(page, timeout=CHAT_TIMEOUT_MS):
    page.wait_for_function(
        "() => { const t = document.querySelector('.chat-input textarea'); return t && !t.disabled; }",
        timeout=timeout)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
        page.on("dialog", lambda d: d.accept("补测意见:折扣政策已更新,15%以上需董事会审批"))
        page.on("console", lambda m: CONSOLE_ERRORS.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
        page.goto(BASE)
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_selector(".login-card", state="visible", timeout=15_000)

        # ===== 张三:F11 反馈 + F9X.1 =====
        login(page, "销售员张三")

        # F11:先发一条新消息,👍 点它,👎 点再前一条非 cancelled 消息
        text, badges, _, _ = send_chat(page, "你好")
        page.wait_for_selector(".toast", state="hidden", timeout=5000)
        page.locator(".msg.agent").last.locator(".fb button").first.click()
        t = toast_text(page)
        record("F11", "👍 反馈", "感谢反馈" in t, f"toast={t!r}")
        page.wait_for_selector(".toast", state="hidden", timeout=5000)
        # 从后往前找一条非 cancelled(带 👍👎 按钮)的消息点 👎
        msgs = page.locator(".msg.agent")
        clicked = False
        for i in range(msgs.count() - 2, -1, -1):
            cand = msgs.nth(i)
            if cand.locator(".fb button").count() >= 2:
                cand.locator(".fb button").nth(1).click()
                clicked = True
                break
        page.wait_for_timeout(1200)
        t = page.locator(".toast").inner_text() if page.locator(".toast").count() else "(无 toast)"
        record("F11", "👎 负反馈(评论生成草稿)", clicked and "已记录" in t, f"toast={t!r}")

        # F9X.1 张三发起 VIP 跟进 → 建任务 + 审批
        text, badges, _, _ = send_chat(
            page, "客户 C001 是 VIP 客户,有笔 ORD-2026-005 待付款订单 45000 元,创建跟进任务并由经理审批")
        m = re.search(r"appr_\w+", text)
        record("F9X.1", "VIP 跟进建任务+触发审批", ("任务" in text or "TASK" in text) and ("审批" in text or m),
               f"审批号={m.group(0) if m else '-'} answer[:120]={text[:120]!r}")
        f9x1_appr = m.group(0) if m else None

        # ===== 赵六:F9 已批准确认 + F9X.1 批准 + F9.5 批量 =====
        login(page, "销售经理赵六")
        click_tab(page, "审批")
        page.wait_for_timeout(1500)
        body = page.locator(".panel:visible .page").inner_text()
        record("F9", "appr_b8fa8deebc9f 已不在待审(上轮已批准)",
               "appr_b8fa8deebc9f" not in body, "")

        if f9x1_appr:
            card = page.locator(".card", has_text=f9x1_appr)
            if card.count():
                card.locator("button", has_text="批准").click()
                page.wait_for_timeout(2500)
                body = page.locator(".panel:visible .page").inner_text()
                record("F9X.1", "经理批准 F9X.1 审批单", "executed" in body or f9x1_appr not in body,
                       f"body[:150]={body[:150]!r}")
            else:
                record("F9X.1", "经理批准 F9X.1 审批单", False, "待审列表无此单")

        # F9.5 批量审批
        click_tab(page, "审批")
        page.wait_for_timeout(1500)
        n = page.locator(".card", has_text="batch_2026_001").count()
        record("F9.5", "批量审批 3 条带 batch 徽标", n == 3, f"实际 {n} 条")
        for i in range(n):
            card = page.locator(".card", has_text="batch_2026_001").first
            card.locator("button", has_text="批准").click()
            page.wait_for_timeout(2500)
        page.wait_for_timeout(2000)
        remaining = page.locator(".card", has_text="batch_2026_001").count()
        record("F9.5", "3 条批量审批全部执行", remaining == 0, f"剩余 {remaining} 条")

        # ===== 钱七:F12 列表数 =====
        login(page, "管理员钱七")
        click_tab(page, "Prompt 管理")
        page.wait_for_timeout(2000)
        names = page.locator(".panel:visible .card .title").all_inner_texts()
        record("F12", "Prompt 列表 11 个", len(names) == 11, f"实际 {len(names)}")

        browser.close()

    passed = sum(1 for r in RESULTS if r[2] is True)
    failed = sum(1 for r in RESULTS if r[2] is False)
    print(f"\n补测汇总 PASS={passed} FAIL={failed}", flush=True)
    with open("eval/e2e_ui_retest_report.txt", "w", encoding="utf-8") as f:
        for fid, desc, ok, detail in RESULTS:
            f.write(f"[{'PASS' if ok else 'FAIL'}] {fid} {desc} | {detail}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
