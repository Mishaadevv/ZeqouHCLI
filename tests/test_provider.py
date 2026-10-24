import json
import unittest

from zeqouhcli.provider import OpenAICompatibleClient


class FakeResponse:
    def __init__(self, events):
        self.events = events

    def __iter__(self):
        records = [("data: " + json.dumps(event) + "\n\n").encode() for event in self.events]
        return iter(records + [b"data: [DONE]\n\n"])


class ProviderStreamTests(unittest.TestCase):
    def test_stream_with_api_usage(self):
        client = OpenAICompatibleClient({"base_url": "https://example.com/v1", "model": "test"})
        events = [
            {"choices": [{"delta": {"content": "Hello"}}]},
            {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 3}},
        ]
        pieces = []
        result = client._consume_sse(FakeResponse(events), [{"role": "user", "content": "Hi"}], pieces.append)
        self.assertEqual(result["content"], "Hello")
        self.assertEqual("".join(pieces), "Hello")
        self.assertEqual(result["usage"], {"input_tokens": 12, "output_tokens": 3})
        self.assertTrue(result["exact_usage"])

    def test_stream_without_usage_uses_estimate(self):
        client = OpenAICompatibleClient({"base_url": "https://example.com/v1", "model": "test"})
        events = [{"choices": [{"delta": {"content": "Hello"}}]}]
        result = client._consume_sse(FakeResponse(events), [{"role": "user", "content": "Hi"}], None)
        self.assertFalse(result["exact_usage"])
        self.assertGreater(result["usage"]["input_tokens"], 0)
        self.assertGreater(result["usage"]["output_tokens"], 0)

    def test_tool_call_chunks_are_combined(self):
        client = OpenAICompatibleClient({"base_url": "https://example.com/v1", "model": "test"})
        events = [
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "type": "function", "function": {"name": "read_", "arguments": '{"path":'}}]}}]},
            {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"name": "file", "arguments": '"a.txt"}'}}]}}]},
        ]
        result = client._consume_sse(FakeResponse(events), [], None)
        self.assertEqual(result["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(result["tool_calls"][0]["function"]["arguments"], '{"path":"a.txt"}')

    def test_reasoning_stream_is_separate_from_answer_text(self):
        client = OpenAICompatibleClient({"base_url": "https://example.com/v1", "model": "test"})
        events = [
            {"choices": [{"delta": {"reasoning_content": "Checking the code. "}}]},
            {"choices": [{"delta": {"content": "The answer is 42."}}]},
        ]
        answers = []
        thoughts = []
        result = client._consume_sse(FakeResponse(events), [], answers.append, thoughts.append)
        self.assertEqual(result["content"], "The answer is 42.")
        self.assertEqual(result["thinking"], "Checking the code. ")
        self.assertEqual("".join(answers), "The answer is 42.")
        self.assertEqual("".join(thoughts), "Checking the code. ")


class ReasoningEffortBodyTests(unittest.TestCase):
    def test_auto_uses_a_declared_effort_value(self):
        client = OpenAICompatibleClient({
            "base_url": "https://example.com/v1",
            "model": "vendor/model",
            "thinking_effort": "auto",
            "model_metadata": {
                "model_id": "vendor/model",
                "reasoning_effort_supported": True,
                "reasoning_parameter": "reasoning_effort",
                "supported_reasoning_efforts": ["low", "high"],
            },
        })
        body = client._request_body([], None, include_usage=False)
        self.assertEqual(body["reasoning_effort"], "low")

    def test_auto_does_not_add_effort_for_unknown_model(self):
        client = OpenAICompatibleClient({"base_url": "https://example.com/v1", "model": "unknown-model", "thinking_effort": "auto"})
        body = client._request_body([], None, include_usage=False)
        self.assertNotIn("reasoning_effort", body)


if __name__ == "__main__":
    unittest.main()
