import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zeqouhcli.agent_tools import ToolRunner, get_tool_definitions
from zeqouhcli.web_tools import WebAccessError, _SearchResultsParser, _VisibleTextParser, validate_public_url


class WebSafetyTests(unittest.TestCase):
    def test_private_ip_is_blocked(self):
        for url in (
            "http://127.0.0.1:8000/",
            "http://10.0.0.1/",
            "http://192.168.1.20/",
            "http://[::1]/",
        ):
            with self.subTest(url=url), self.assertRaises(WebAccessError):
                validate_public_url(url, resolve_dns=False)

    def test_non_http_scheme_is_blocked(self):
        with self.assertRaises(WebAccessError):
            validate_public_url("file:///etc/passwd", resolve_dns=False)

    def test_public_https_url_is_normalized(self):
        self.assertEqual(
            validate_public_url("https://example.com", resolve_dns=False),
            "https://example.com/",
        )

    def test_html_reader_extracts_title_and_visible_text(self):
        parser = _VisibleTextParser()
        parser = _VisibleTextParser(base_url="https://example.com/docs")
        parser.feed("<html><head><title>Sample page</title><script>secret()</script></head><body><h1>Hello</h1><p>Readable text</p><a href='/reference'>Reference docs</a></body></html>")
        self.assertEqual(parser.title, "Sample page")
        self.assertIn("Hello", parser.text)
        self.assertIn("Readable text", parser.text)
        self.assertNotIn("secret", parser.text)
        self.assertEqual(parser.links[0]["url"], "https://example.com/reference")
        self.assertEqual(parser.links[0]["text"], "Reference docs")

    def test_search_parser_extracts_result_title_and_redirect_url(self):
        parser = _SearchResultsParser()
        parser.feed('<a class="result__a" href="https://example.com/article">Example article</a>')
        self.assertEqual(parser.results, [{"url": "https://example.com/article", "title": "Example article"}])

    def test_web_tools_are_filtered_when_disabled(self):
        enabled = {item["function"]["name"] for item in get_tool_definitions(True)}
        disabled = {item["function"]["name"] for item in get_tool_definitions(False)}
        self.assertIn("web_search", enabled)
        self.assertIn("web_open", enabled)
        self.assertNotIn("web_search", disabled)
        self.assertNotIn("web_open", disabled)

    def test_web_tool_runner_respects_toggle(self):
        with tempfile.TemporaryDirectory() as tmp:
            runner = ToolRunner(Path(tmp), web_enabled=False)
            self.assertIn("web access is disabled", runner.execute("web_search", {"query": "example"}).lower())

    def test_web_open_tool_delegates_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp, patch("zeqouhcli.agent_tools.web_open", return_value="Title: Test\nURL: https://example.com/\n\nText") as open_mock:
            runner = ToolRunner(Path(tmp), web_enabled=True)
            self.assertIn("Title: Test", runner.execute("web_open", {"url": "https://example.com/"}))
            open_mock.assert_called_once_with("https://example.com/")


if __name__ == "__main__":
    unittest.main()
