# -*- coding: utf-8 -*-
"""最终补测:F11 👎 负反馈生成草稿、F9.5 批量审批 UI 执行。"""
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "eval"))
from playwright.sync_api import sync_playwright

import e2e_ui_f1_f14 as base
from e2e_ui_f1_f14 import (
    BASE, CONSOLE_ERRORS, RESULTS, click_tab, login, record, send_chat, toast_text,
)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
        page.on("dialog", lambda d: d.accept("折扣政策已更新,15%以上需董事会审批"))
        page.on("pageerror", lambda e: CONSOLE_ERRORS.append(str(e)))
        page.goto(BASE)
        page.evaluate("localStorage.clear()")
        page.reload()
        page.wait_for_selector(".login-card", state="visible", timeout=15_000)

        # F11 👎:张三登录,发一条消息,直接点踩(带评论)
        login(page, "销售员张三")
        send_chat(page, "你好")
        page.wait_for_selector(".toast", state="hidden", timeout=5000)
        page.locator(".msg.agent").last.locator(".fb button").nth(1).click()
        t = toast_text(page)
        record("F11", "👎 负反馈(评论生成草稿)", "已记录" in t, f"toast={t!r}")

        # F9.5:赵六登录,按 summary 找到 3 条批量审批并逐条批准
        login(page, "销售经理赵六")
        click_tab(page, "审批")
        page.wait_for_timeout(2000)
        summaries = ["为客户 C001 创建季度跟进任务", "通知经理赵六关于 C001 的跟进安排", "为 C001 创建售后协调工单"]
        for s in summaries:
            card = page.locator(".panel:visible .card", has_text=s)
            if card.count() == 0:
                record("F9.5", f"批准「{s}」", False, "卡片不存在")
                continue
            badge = card.locator(".badge.purple").count()
            card.locator("button", has_text="批准").click()
            page.wait_for_timeout(2500)
            body = page.locator(".panel:visible .page").inner_text()
            still = page.locator(".panel:visible .card", has_text=s).count()
            record("F9.5", f"批准「{s}」", still == 0 or "executed" in body,
                   f"batch徽标数={badge} 批准后可仍然见={still}")
        browser.close()

    passed = sum(1 for r in RESULTS if r[2] is True)
    failed = sum(1 for r in RESULTS if r[2] is False)
    print(f"\n最终补测 PASS={passed} FAIL={failed}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
