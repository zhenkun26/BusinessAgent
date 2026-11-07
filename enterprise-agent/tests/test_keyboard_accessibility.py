"""F2-07 source semantics only; no DOM, browser or assistive-technology claim."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text()
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr"}


class Template(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.nodes: list[dict] = []
        self.stack: list[dict] = []
        self.duplicates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        names = [key for key, _ in attrs]
        if len(names) != len(set(names)):
            self.duplicates.append(tag)
        node = {"tag": tag, "attrs": dict(attrs), "ancestors": list(self.stack)}
        self.nodes.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                self.stack = self.stack[:i]
                break


class KeyboardTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = Template()
        self.template.feed(HTML)
        self.nodes = self.template.nodes

    def find(self, **attrs: str) -> dict:
        matches = [n for n in self.nodes if all(n["attrs"].get(k) == v for k, v in attrs.items())]
        self.assertEqual(len(matches), 1, attrs)
        return matches[0]

    def test_no_duplicate_attributes_or_nested_buttons(self) -> None:
        self.assertEqual(self.template.duplicates, [])
        for node in self.nodes:
            if node["tag"] == "button":
                self.assertFalse(any(p["tag"] == "button" for p in node["ancestors"]))

    def test_action_handlers_have_native_keyboard_semantics(self) -> None:
        actions = [n for n in self.nodes if any(k.startswith("@click=") or k == "@click"
                   for k in n["attrs"])]
        self.assertGreater(len(actions), 25)
        for node in actions:
            with self.subTest(handler=node["attrs"].get("@click")):
                self.assertEqual(node["tag"], "button")
                self.assertNotIn("tabindex", node["attrs"])
        self.assertNotIn('role="menu"', HTML)
        self.assertNotIn('role="tab"', HTML)

    def test_every_input_has_associated_or_contextual_name(self) -> None:
        labels = [n["attrs"] for n in self.nodes if n["tag"] == "label"]
        for node in self.nodes:
            if node["tag"] not in {"input", "textarea"}:
                continue
            a = node["attrs"]
            with self.subTest(model=a.get("v-model", a.get("v-model.number"))):
                named = bool(a.get("aria-label") or a.get(":aria-label"))
                named |= any(a.get("id") and label.get("for") == a["id"] for label in labels)
                named |= any(a.get(":id") and label.get(":for") == a[":id"] for label in labels)
                self.assertTrue(named)
        self.assertEqual(self.find(id="login-password")["attrs"]["autocomplete"], "current-password")
        self.assertEqual(self.find(id="login-name")["attrs"]["autocomplete"], "username")

    def test_disclosures_expose_state_targets_and_escape(self) -> None:
        for trigger, target, handler in (("accountPicker", "account-options", "closePicker"),
                                         ("sceneTrigger", "scene-options", "closeScenes")):
            with self.subTest(trigger=trigger):
                node = self.find(ref=trigger)
                self.assertEqual(node["tag"], "button")
                self.assertIn(":aria-expanded", node["attrs"])
                self.assertEqual(node["attrs"]["aria-controls"], target)
                group = self.find(id=target)
                self.assertEqual(group["attrs"]["role"], "group")
                self.assertEqual(group["attrs"]["@keydown.esc.stop.prevent"], handler)
        self.assertEqual(self.find(ref="sceneTrigger")["attrs"]["@keydown.esc.stop.prevent"], "closeScenes")

    def test_login_submission_and_composition_are_bound(self) -> None:
        form = self.find(**{"@submit.prevent": "doLogin"})
        self.assertEqual(form["tag"], "form")
        submit = [n for n in self.nodes if n["tag"] == "button" and n["attrs"].get("type") == "submit"]
        self.assertEqual(len(submit), 1)
        self.assertIn(form, submit[0]["ancestors"])
        draft = self.find(id="chat-draft")["attrs"]
        self.assertEqual(draft["@keydown"], "onDraftKeydown")
        self.assertEqual(draft["@compositionstart"], "composing=true")
        self.assertEqual(draft["@compositionend"], "composing=false")
        self.assertNotIn("@keydown.enter.exact.prevent", draft)
        self.assertIn("chat-input-hint", draft["aria-describedby"])

    def test_transcript_tokens_and_timer_are_outside_live_regions(self) -> None:
        transcript = self.find(id="chat-transcript")
        self.assertEqual(transcript["attrs"]["role"], "region")
        self.assertEqual(transcript["attrs"]["aria-label"], "对话记录")
        self.assertEqual(transcript["attrs"]["tabindex"], "0")
        self.assertNotIn("aria-live", transcript["attrs"])
        for node in [transcript, self.find(ref="chatProgress")]:
            self.assertFalse(any(p["attrs"].get("aria-live") or p["attrs"].get("role")
                                 in {"status", "alert", "log"} for p in node["ancestors"]))
        status = self.find(id="chat-status")["attrs"]
        self.assertEqual(status["role"], "status")
        self.assertEqual(status["aria-live"], "polite")
        self.assertEqual(status["aria-atomic"], "true")
        self.assertNotIn("v-if", status)
        self.assertEqual(self.find(id="login-error")["attrs"]["role"], "alert")

    def test_navigation_and_repeated_actions_identify_current_target(self) -> None:
        nav = self.find(**{"aria-label": "主导航"})
        buttons = [n for n in self.nodes if n["tag"] == "button" and nav in n["ancestors"]]
        self.assertEqual(len(buttons), 5)
        for button in buttons:
            self.assertIn(":aria-current", button["attrs"])
        for node in self.nodes:
            action = node["attrs"].get("@click", "")
            if action.startswith(("sendFeedback(", "decide(", "resume(", "ask(",
                                  "createVersion(", "activate(", "setTraffic(")):
                self.assertIn(":aria-label", node["attrs"], action)
        for method in ("loadApprovals", "loadHandled", "loadMine", "loadPrompts", "loadStatus"):
            self.assertIn("aria-label", self.find(**{"@click": method})["attrs"])

    def test_focus_targets_have_no_positive_tab_order_and_keep_visible_indicator(self) -> None:
        for node in self.nodes:
            value = node["attrs"].get("tabindex")
            if value is not None:
                self.assertIn(value, {"-1", "0"})
        for name in ("chatHeading", "approvalHeading", "mineHeading", "promptHeading",
                     "referenceHeading", "statusHeading", "chatProgress"):
            self.assertEqual(self.find(ref=name)["attrs"]["tabindex"], "-1")
        self.assertIn("#app :focus-visible { outline: 3px solid", HTML)


if __name__ == "__main__":
    unittest.main(verbosity=2)
