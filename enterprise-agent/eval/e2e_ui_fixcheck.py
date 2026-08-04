# -*- coding: utf-8 -*-
"""修复验证:F10 全新会话首轮取消 + F9.5 batch 紫色徽标。"""
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "eval"))
from playwright.sync_api import sync_playwright

import e2e_ui_f1_f14 as base
from e2e_ui_f1_f14 import (
    BASE, CHAT_TIMEOUT_MS, RESULTS, click_tab, last_agent, login, record, toast_text,
)


def wait_idle(page, timeout=CHAT_TIMEOUT_MS):
    page.wait_for_function(
        "() => { const t = document.querySelector('.chat-input textarea'); return t && !t.disabled; }",
        timeout=timeout)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
        page.on("dialog", lambda d: d.accept(""))
        page.goto(BASE)
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_selector(".login-card", state="visible", timeout=15_000)

        # F10 修复验证:全新会话首轮立即取消
        login(page, "销售员张三")
        page.fill(".chat-input textarea", "公司的折扣审批政策是怎样的")
        page.click(".chat-input .btn")
        page.wait_for_selector(".pending-bar", state="visible", timeout=10_000)
        page.wait_for_timeout(3000)
        page.click(".pending-bar .btn-danger")
        t = toast_text(page)
        wait_idle(page)
        text, badges, _ = last_agent(page)
        record("修复2", "全新会话首轮点取消生效",
               "已请求取消" in t and any("cancelled" in b for b in badges),
               f"toast={t!r} badges={badges} answer[:60]={text[:60]!r}")

        # F9.5 修复验证:batch 紫色徽标出现
        login(page, "销售经理赵六")
        click_tab(page, "审批")
        page.wait_for_timeout(2000)
        badges = page.locator(".panel:visible .card .badge.purple").all_inner_texts()
        n_batch = sum(1 for b in badges if "batch_2026_001" in b)
        record("修复4", "审批卡片显示 batch 紫色徽标", n_batch == 3,
               f"batch徽标数={n_batch} badges={badges}")
        browser.close()

    passed = sum(1 for r in RESULTS if r[2] is True)
    failed = sum(1 for r in RESULTS if r[2] is False)
    print(f"\n修复验证 PASS={passed} FAIL={failed}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
