#!/usr/bin/env python3
"""Dry-run test for gateway.py without a real upstream model."""
import os
import sys
import json


class MockUsage:
    prompt_tokens = 12
    completion_tokens = 8
    total_tokens = 20


class MockFunction:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class MockToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.function = MockFunction(name, arguments)


class MockToolCallDelta:
    def __init__(self, index, id=None, name=None, arguments=None):
        self.index = index
        self.id = id
        self.function = MockFunction(name, arguments)


class MockDelta:
    def __init__(self, content=None, tool_calls=None, role=None):
        self.content = content
        self.tool_calls = tool_calls
        self.role = role


class MockMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class MockChoice:
    def __init__(self, delta=None, message=None, finish=None):
        self.delta = delta
        self.message = message
        self.finish_reason = finish


class MockChunk:
    def __init__(self, delta=None, finish=None, usage=None):
        self.choices = [MockChoice(delta=delta, finish=finish)] if delta else []
        self.usage = usage


class MockCompletion:
    def __init__(self, content=None, tool_calls=None):
        self.choices = [MockChoice(message=MockMessage(content, tool_calls), finish="stop")]
        self.usage = MockUsage()


class MockCompletions:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs):
        if kwargs.get("stream"):
            chunks = [
                MockChunk(MockDelta(content="I'll ")),
                MockChunk(MockDelta(content="search for it.")),
                MockChunk(
                    MockDelta(
                        tool_calls=[
                            MockToolCallDelta(0, id="call_abc", name="web_search"),
                            MockToolCallDelta(0, arguments='{"q'),
                            MockToolCallDelta(0, arguments='uery": "latest news"}'),
                        ]
                    ),
                    finish="tool_calls",
                    usage=MockUsage(),
                ),
            ]
            return (c for c in chunks)
        else:
            return MockCompletion("Hello from non-streaming")


class MockClient:
    def __init__(self, *args, **kwargs):
        self.completions = MockCompletions(self)

    @property
    def chat(self):
        return self


class MockOpenAI:
    OpenAI = MockClient
    APIError = Exception


class MockDotenv:
    @staticmethod
    def load_dotenv(*args, **kwargs):
        pass


sys.modules["openai"] = MockOpenAI
sys.modules["dotenv"] = MockDotenv

os.environ["CODEBUDDY_BASE_URL"] = "http://127.0.0.1:8001/codebuddy/v1"
os.environ["CODEBUDDY_API_KEY"] = "dummy"

# Import the gateway after mocking. The file name contains hyphens, so it
# cannot be imported with a normal `import` statement; load it by path.
import importlib.util
import os as _os

_spec = importlib.util.spec_from_file_location(
    "codex_buddy_gateway",
    _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "codex-buddy-gateway.py"),
)
gateway = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gateway)
from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(gateway.app)

print("=== Test streaming response ===")
resp = client.post(
    "/v1/responses",
    json={
        "model": "kimi-k3",
        "input": "Find latest news",
        "stream": True,
    },
)
assert resp.status_code == 200, resp.text
seen_events = []
for line in resp.text.splitlines():
    if line.startswith("data: "):
        data = json.loads(line[6:])
        seen_events.append(data["type"])
        print(data["type"])

expected = [
    "response.created",
    "response.output_item.added",
    "response.content_part.added",
    "response.output_text.delta",
    "response.output_text.delta",
    "response.content_part.done",
    "response.output_item.done",
    "response.output_item.added",
    "response.function_call_arguments.delta",
    "response.function_call_arguments.delta",
    "response.output_item.done",
    "response.completed",
]
assert seen_events == expected, f"Unexpected events: {seen_events}"

print("\n=== Test non-streaming response ===")
resp2 = client.post(
    "/v1/responses",
    json={
        "model": "kimi-k3",
        "input": "Hello",
        "stream": False,
    },
)
assert resp2.status_code == 200, resp2.text
body = resp2.json()
assert body["status"] == "completed"
assert body["output"][0]["type"] == "message"
print(json.dumps(body, indent=2, ensure_ascii=False))

print("\nAll gateway dry-run checks passed.")
