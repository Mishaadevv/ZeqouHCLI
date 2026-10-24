import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zeqouhcli.config import endpoint_for, models_endpoint_for
from zeqouhcli.paths import is_within
from zeqouhcli.sessions import estimate_messages_tokens, estimate_tokens
from zeqouhcli.agent_tools import ToolRunner
from zeqouhcli.app import SlashCommandCompleter, ZeqouCLI
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document


class TokenEstimateTests(unittest.TestCase):
    def test_empty_text(self):
        self.assertEqual(estimate_tokens(""), 0)

    def test_non_empty_text(self):
        self.assertEqual(estimate_tokens("abcd"), 1)
        self.assertEqual(estimate_tokens("abcde"), 2)

    def test_messages_estimate_is_positive(self):
        messages = [{"role": "user", "content": "Hello"}]
        self.assertGreater(estimate_messages_tokens(messages), 0)


class EndpointTests(unittest.TestCase):
    def test_base_url(self):
        self.assertEqual(endpoint_for("https://example.com/v1/"), "https://example.com/v1/chat/completions")

    def test_full_endpoint(self):
        url = "https://example.com/v1/chat/completions"
        self.assertEqual(endpoint_for(url), url)

    def test_models_endpoint(self):
        self.assertEqual(models_endpoint_for("https://example.com/v1"), "https://example.com/v1/models")
        self.assertEqual(models_endpoint_for("https://example.com/v1/chat/completions"), "https://example.com/v1/models")


class PathGuardTests(unittest.TestCase):
    def test_inside_path_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(is_within(root / "a.txt", root))

    def test_outside_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            self.assertFalse(is_within(Path(outside) / "a.txt", Path(tmp)))


class SlashCompleterTests(unittest.TestCase):
    def test_completes_commands_only_for_slash_prefix(self):
        completer = SlashCommandCompleter()
        completions = list(completer.get_completions(Document("/con"), CompleteEvent()))
        self.assertIn("connect", [item.text for item in completions])
        self.assertEqual(list(completer.get_completions(Document("fix this"), CompleteEvent())), [])


class PromptRenderingTests(unittest.TestCase):
    def test_prompt_uses_prompt_toolkit_formatted_text_not_html(self):
        class FakePromptSession:
            def prompt(self, message, bottom_toolbar=None):
                # Converting the message must not raise an XML/HTML parser error.
                rendered = to_formatted_text(message)
                self.message = rendered
                return "test input"

        cli = ZeqouCLI.__new__(ZeqouCLI)
        cli.prompt_session = FakePromptSession()
        cli.bottom_toolbar = lambda: []
        self.assertEqual(cli.read_prompt(), "test input")
        self.assertEqual(list(cli.prompt_session.message), [("class:prompt", "❯ ")])


class ToolRunnerTests(unittest.TestCase):
    def test_write_requires_approval_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = ToolRunner(root, permissions="ask", ask=lambda _message: False)
            result = runner.execute("write_file", {"path": "test.txt", "content": "hello"})
            self.assertIn("Cancelled", result)
            self.assertFalse((root / "test.txt").exists())

    def test_write_succeeds_after_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = ToolRunner(root, permissions="ask", ask=lambda _message: True)
            result = runner.execute("write_file", {"path": "nested/test.txt", "content": "hello"})
            self.assertIn("Wrote 5 characters", result)
            self.assertEqual((root / "nested" / "test.txt").read_text(), "hello")

    def test_tool_blocks_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            runner = ToolRunner(root)
            result = runner.execute("read_file", {"path": str(Path(outside) / "secret.txt")})
            self.assertIn("Blocked", result)

    def test_edit_file_replaces_exact_snippet_and_previews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "app.py"
            target.write_text("value = 1\n", encoding="utf-8")
            previews = []
            runner = ToolRunner(
                root,
                permissions="ask",
                ask=lambda _message: True,
                on_write_preview=lambda path, old, new: previews.append((path, old, new)),
            )
            result = runner.execute("edit_file", {
                "path": "app.py", "old_string": "value = 1", "new_string": "value = 2"
            })
            self.assertIn("Wrote", result)
            self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")
            self.assertEqual(previews[0][1], "value = 1\n")
            self.assertEqual(previews[0][2], "value = 2\n")

    def test_edit_file_rejects_ambiguous_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "app.py"
            target.write_text("x = 1\nx = 1\n", encoding="utf-8")
            runner = ToolRunner(root, permissions="auto")
            result = runner.execute("edit_file", {
                "path": "app.py", "old_string": "x = 1", "new_string": "x = 2"
            })
            self.assertIn("matched 2 places", result)
            self.assertEqual(target.read_text(encoding="utf-8"), "x = 1\nx = 1\n")


class SettingsCommandTests(unittest.TestCase):
    class FakeConfigStore:
        def __init__(self, data):
            self.data = data
            self.saves = 0

        def save(self):
            self.saves += 1

    def test_settings_toggle_persists_boolean_setting(self):
        cli = ZeqouCLI.__new__(ZeqouCLI)
        cli.config = {"show_thinking": True}
        cli.config_store = self.FakeConfigStore(cli.config)
        cli.settings_command("thinking", "off")
        self.assertFalse(cli.config["show_thinking"])
        self.assertEqual(cli.config_store.saves, 1)

    def test_settings_sets_search_result_count(self):
        cli = ZeqouCLI.__new__(ZeqouCLI)
        cli.config = {"web_search_results": 5}
        cli.config_store = self.FakeConfigStore(cli.config)
        cli.settings_command("web_results", "8")
        self.assertEqual(cli.config["web_search_results"], 8)
        self.assertEqual(cli.config_store.saves, 1)


class SessionSeparationTests(unittest.TestCase):
    def test_new_command_swaps_to_a_distinct_empty_session_and_redraws(self):
        cli = ZeqouCLI.__new__(ZeqouCLI)
        cli.session = {"id": "old-session", "title": "Old", "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "old question"}]}
        cli._save = lambda: None
        cli._new_session = lambda title="New session": {"id": "new-session", "title": title, "messages": [{"role": "system", "content": "sys"}]}
        redraws = []
        cli.redraw_session_view = lambda **kwargs: redraws.append(kwargs)
        cli.handle_command("/new Fresh topic")
        self.assertEqual(cli.session["id"], "new-session")
        self.assertEqual(cli.session["messages"], [{"role": "system", "content": "sys"}])
        self.assertEqual(redraws[0]["resumed"], False)

    def test_resume_without_id_skips_current_empty_session(self):
        cli = ZeqouCLI.__new__(ZeqouCLI)
        cli.session = {"id": "new-session", "title": "New session", "messages": [{"role": "system", "content": "sys"}]}
        cli.sessions = type("Store", (), {"list": lambda _self: [
            {"id": "new-session", "title": "New session", "messages": [{"role": "system", "content": "sys"}]},
            {"id": "previous-session", "title": "Previous", "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "earlier"}]},
        ]})()
        cli._save = lambda: None
        redraws = []
        cli.redraw_session_view = lambda **kwargs: redraws.append(kwargs)
        cli.handle_command("/resume")
        self.assertEqual(cli.session["id"], "previous-session")
        self.assertEqual(redraws[0]["resumed"], True)

    def test_local_image_reference_becomes_multimodal_payload(self):
        import base64
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_bytes = b"\x89PNG\r\n\x1a\nimage-data"
            (root / "screen.png").write_bytes(image_bytes)
            cli = ZeqouCLI.__new__(ZeqouCLI)
            cli.cwd = root
            original = [{"role": "user", "content": [
                {"type": "text", "text": "Inspect this"},
                {"type": "zeqou_image_ref", "path": "screen.png", "mime_type": "image/png"},
            ]}]
            outgoing = cli._messages_for_api(original, allow_images=True)
            image_part = outgoing[0]["content"][1]
            self.assertEqual(image_part["type"], "image_url")
            self.assertEqual(image_part["image_url"]["url"], "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii"))
            self.assertEqual(original[0]["content"][1]["type"], "zeqou_image_ref")

    def test_image_reference_is_not_sent_to_text_only_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "screen.png").write_bytes(b"png")
            cli = ZeqouCLI.__new__(ZeqouCLI)
            cli.cwd = root
            messages = [{"role": "user", "content": [{"type": "zeqou_image_ref", "path": "screen.png", "mime_type": "image/png"}]}]
            outgoing = cli._messages_for_api(messages, allow_images=False)
            self.assertEqual(outgoing[0]["content"][0]["type"], "text")
            self.assertIn("not configured for vision", outgoing[0]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
