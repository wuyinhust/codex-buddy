#!/usr/bin/env python3
"""
codex-buddy-gateway
====================
A minimal local gateway that translates OpenAI's **Responses API**
(what the Codex App / CLI speak) into standard OpenAI-compatible
**Chat Completions** (what CodeBuddy2api / CodeBuddy expose).

This lets you run Codex against CodeBuddy's model library WITHOUT opencodex.

Run:
    python codex-buddy-gateway.py

Then point Codex at:
    http://127.0.0.1:8787/v1

with `wire_api = "responses"` (or the equivalent Codex setting).

Environment variables (or a `.env` file):
    CODEBUDDY_BASE_URL      # upstream Chat Completions base URL
                            # default: http://127.0.0.1:8001/codebuddy/v1
    CODEBUDDY_API_KEY       # default: dummy (CodeBuddy2api usually handles auth)
    CODEBUDDY_MODEL         # default model when the request omits one
                            # default: kimi-k3
    GATEWAY_HOST            # default: 127.0.0.1
    GATEWAY_PORT            # default: 8787
"""

import os
import json
import time
import secrets
import sys
import importlib.util
from typing import Any, Dict, List, Optional, Generator
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import openai

load_dotenv()


# ---------- configuration ----------

CODEBUDDY_BASE_URL = os.getenv("CODEBUDDY_BASE_URL", "http://127.0.0.1:8001/codebuddy/v1")
CODEBUDDY_API_KEY = os.getenv("CODEBUDDY_API_KEY", "dummy")
CODEBUDDY_MODEL = os.getenv("CODEBUDDY_MODEL", "kimi-k3")
GATEWAY_HOST = os.getenv("GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "8787"))
ORCHESTRATE = os.getenv("CODEBUDDY_ORCHESTRATE", "0").lower() in {"1", "true", "yes", "on"}


def run_orchestrated_turn(body: Dict[str, Any]) -> Dict[str, Any]:
    """Run one Codex turn through GPT planner -> CodeBuddy workers -> GPT review.

    This is opt-in so the gateway remains a transparent Responses bridge by default.
    The existing orchestrator owns provider selection and worker fallback; the whole
    translated conversation is supplied as the task context for this turn.
    """
    module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpt-kimi-orchestrator.py")
    spec = importlib.util.spec_from_file_location("codex_buddy_orchestrator", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load gpt-kimi-orchestrator.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    messages = translate_input(body.get("input"))
    conversation = "\n\n".join(
        f"{message.get('role', 'user').upper()}: {message.get('content', '')}"
        for message in messages
    )
    task = (
        "Work on the user's current Codex conversation. Preserve the conversation context "
        "and return a useful final answer. Delegate implementation/research sub-tasks to "
        "the configured CodeBuddy worker models.\n\nCONVERSATION:\n" + conversation
    )

    orchestrator = module.Orchestrator()
    tasks = orchestrator.plan(task)
    # If the planner returns no work, still let the reviewer answer the conversation.
    if tasks:
        orchestrator.execute(tasks)
    answer = orchestrator.review(task)
    return {
        "id": generate_response_id(),
        "object": "response",
        "created_at": now_ts(),
        "status": "completed",
        "model": os.getenv("ORCHESTRATOR_MODEL", "gpt-4o-mini"),
        "output": [{
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": answer}],
        }],
    }


def orchestrated_sse(body: Dict[str, Any]) -> Generator[str, None, None]:
    """Expose the orchestrated result as the small Responses SSE sequence Codex needs."""
    response = run_orchestrated_turn(body)
    output = response["output"][0]
    text = output["content"][0]["text"]
    yield sse_event("response.created", {"type": "response.created", "response": response})
    yield sse_event("response.output_item.added", {
        "type": "response.output_item.added", "output_index": 0,
        "item": {"type": "message", "role": "assistant", "status": "in_progress"},
    })
    yield sse_event("response.content_part.added", {
        "type": "response.content_part.added", "output_index": 0,
        "content_index": 0, "part": {"type": "output_text", "text": ""},
    })
    if text:
        yield sse_event("response.output_text.delta", {
            "type": "response.output_text.delta", "output_index": 0,
            "content_index": 0, "delta": text,
        })
    yield sse_event("response.content_part.done", {
        "type": "response.content_part.done", "output_index": 0, "content_index": 0,
    })
    yield sse_event("response.output_item.done", {
        "type": "response.output_item.done", "output_index": 0, "item": output,
    })
    yield sse_event("response.completed", {"type": "response.completed", "response": response})


# ---------- small helpers ----------

def generate_response_id() -> str:
    return "resp_" + secrets.token_hex(12)


def now_ts() -> int:
    return int(time.time())


def sse_event(event_type: str, data: Any) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def extract_text(content: Any) -> str:
    """Extract plain text from a Responses API content object or a raw string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") in ("input_text", "output_text", "text"):
                    parts.append(part.get("text", ""))
        return "\n".join(parts)
    return str(content)


# ---------- Responses API input -> Chat Completions messages ----------

def translate_input(input_data: Any) -> List[Dict[str, Any]]:
    """Translate a Responses API `input` into Chat Completions `messages`."""
    if isinstance(input_data, str):
        return [{"role": "user", "content": input_data}]
    if not isinstance(input_data, list):
        return [{"role": "user", "content": str(input_data)}]

    messages: List[Dict[str, Any]] = []
    for item in input_data:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type", "message")

        if item_type == "message":
            role = item.get("role", "user")
            # Chat Completions has no "developer" role; map it to "system".
            if role == "developer":
                role = "system"
            messages.append({"role": role, "content": extract_text(item.get("content"))})

        elif item_type == "function_call_output":
            messages.append({
                "role": "tool",
                "content": item.get("output", ""),
                "tool_call_id": item.get("call_id", "call_" + str(len(messages))),
            })

        # reasoning / other unsupported item types are skipped.
    return messages


def translate_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Translate Responses API tool definitions into Chat Completions format."""
    if not tools:
        return None
    chat_tools: List[Dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        ttype = tool.get("type", "function")
        if ttype == "function":
            chat_tools.append(tool)
        elif ttype == "custom":
            fn = tool.get("custom", {})
            if "name" in fn:
                chat_tools.append({
                    "type": "function",
                    "function": {
                        "name": fn.get("name", ""),
                        "description": fn.get("description", ""),
                        "parameters": fn.get("parameters", {}),
                    },
                })
    return chat_tools or None


def translate_tool_choice(tool_choice: Any) -> Any:
    """Translate Responses API `tool_choice` into Chat Completions format."""
    if tool_choice is None:
        return None
    if isinstance(tool_choice, str):
        return tool_choice
    if isinstance(tool_choice, dict):
        ttype = tool_choice.get("type")
        if ttype in ("auto", "none", "required"):
            return ttype
        if ttype == "tool":
            name = tool_choice.get("name") or (tool_choice.get("tool", {}) or {}).get("name")
            if name:
                return {"type": "function", "function": {"name": name}}
    return "auto"


def build_chat_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    """Build a Chat Completions request body from a Responses API request body."""
    payload: Dict[str, Any] = {
        "model": body.get("model", CODEBUDDY_MODEL),
        "messages": translate_input(body.get("input")),
    }

    tools = translate_tools(body.get("tools"))
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = translate_tool_choice(body.get("tool_choice"))

    for key in ("temperature", "top_p", "max_tokens", "parallel_tool_calls"):
        if key in body:
            payload[key] = body[key]

    payload["stream"] = body.get("stream", True)
    if payload["stream"]:
        payload["stream_options"] = {"include_usage": True}

    return payload


# ---------- Chat Completions -> Responses API translation (non-streaming) ----------

def build_response_output(message: Any) -> List[Dict[str, Any]]:
    """Turn a Chat Completions message into Responses API output items."""
    output: List[Dict[str, Any]] = []
    content = message.content
    if content:
        output.append({
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": content}],
        })

    for tc in message.tool_calls or []:
        output.append({
            "type": "function_call",
            "id": tc.id,
            "call_id": tc.id,
            "name": tc.function.name,
            "arguments": tc.function.arguments,
            "status": "completed",
        })

    return output


def translate_usage(usage: Any) -> Optional[Dict[str, int]]:
    if usage is None:
        return None
    return {
        "input_tokens": getattr(usage, "prompt_tokens", 0),
        "output_tokens": getattr(usage, "completion_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
    }


# ---------- streaming translation ----------

def _emit_completed_text(text_state: Dict[str, Any], output_items: List[Dict[str, Any]]) -> None:
    """Append a completed text message item to `output_items`."""
    output_items.append({
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text_state["content"]}],
    })


def stream_events(body: Dict[str, Any]) -> Generator[str, None, None]:
    """Stream Responses API SSE events built from a Chat Completions stream."""
    client = openai.OpenAI(base_url=CODEBUDDY_BASE_URL, api_key=CODEBUDDY_API_KEY)
    payload = build_chat_payload(body)
    response_id = generate_response_id()
    model = payload["model"]

    yield sse_event(
        "response.created",
        {
            "type": "response.created",
            "response": {
                "id": response_id,
                "object": "response",
                "created_at": now_ts(),
                "status": "in_progress",
                "model": model,
            },
        },
    )

    text_state: Optional[Dict[str, Any]] = None
    text_done = False
    tool_states: Dict[int, Dict[str, Any]] = {}
    next_output_index = 0
    usage: Optional[Dict[str, int]] = None
    output_items: List[Dict[str, Any]] = []

    try:
        for chunk in client.chat.completions.create(**payload):
            choice = chunk.choices[0] if chunk.choices else None
            delta = choice.delta if choice else None
            finish = choice.finish_reason if choice else None

            if delta:
                # ---- text content ----
                if delta.content:
                    if text_state is None:
                        text_state = {"output_index": next_output_index, "content": ""}
                        next_output_index += 1
                        yield sse_event(
                            "response.output_item.added",
                            {
                                "type": "response.output_item.added",
                                "output_index": text_state["output_index"],
                                "item": {
                                    "type": "message",
                                    "role": "assistant",
                                    "status": "in_progress",
                                },
                            },
                        )
                        yield sse_event(
                            "response.content_part.added",
                            {
                                "type": "response.content_part.added",
                                "output_index": text_state["output_index"],
                                "content_index": 0,
                                "part": {"type": "output_text", "text": ""},
                            },
                        )
                    text_state["content"] += delta.content
                    yield sse_event(
                        "response.output_text.delta",
                        {
                            "type": "response.output_text.delta",
                            "output_index": text_state["output_index"],
                            "content_index": 0,
                            "delta": delta.content,
                        },
                    )

                # ---- tool calls ----
                if delta.tool_calls:
                    # Finalize the text message before a tool call begins.
                    if text_state is not None and not text_done:
                        text_done = True
                        _emit_completed_text(text_state, output_items)
                        yield sse_event(
                            "response.content_part.done",
                            {
                                "type": "response.content_part.done",
                                "output_index": text_state["output_index"],
                                "content_index": 0,
                            },
                        )
                        yield sse_event(
                            "response.output_item.done",
                            {
                                "type": "response.output_item.done",
                                "output_index": text_state["output_index"],
                                "item": output_items[-1],
                            },
                        )

                    for tc in delta.tool_calls:
                        idx = tc.index
                        state = tool_states.setdefault(
                            idx,
                            {
                                "id": None,
                                "name": "",
                                "arguments": "",
                                "last_args": "",
                                "added": False,
                                "output_index": None,
                            },
                        )
                        if tc.id:
                            state["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                state["name"] += tc.function.name
                            if tc.function.arguments:
                                state["arguments"] += tc.function.arguments

                        if not state["added"] and state["id"] and state["name"]:
                            state["added"] = True
                            state["output_index"] = next_output_index
                            next_output_index += 1
                            yield sse_event(
                                "response.output_item.added",
                                {
                                    "type": "response.output_item.added",
                                    "output_index": state["output_index"],
                                    "item": {
                                        "type": "function_call",
                                        "id": state["id"],
                                        "call_id": state["id"],
                                        "name": state["name"],
                                        "arguments": "",
                                        "status": "in_progress",
                                    },
                                },
                            )

                        if state["added"]:
                            args_delta = state["arguments"][len(state["last_args"]):]
                            state["last_args"] = state["arguments"]
                            if args_delta:
                                yield sse_event(
                                    "response.function_call_arguments.delta",
                                    {
                                        "type": "response.function_call_arguments.delta",
                                        "output_index": state["output_index"],
                                        "delta": args_delta,
                                    },
                                )

            if finish:
                # finalize text item
                if text_state is not None and not text_done:
                    text_done = True
                    _emit_completed_text(text_state, output_items)
                    yield sse_event(
                        "response.content_part.done",
                        {
                            "type": "response.content_part.done",
                            "output_index": text_state["output_index"],
                            "content_index": 0,
                        },
                    )
                    yield sse_event(
                        "response.output_item.done",
                        {
                            "type": "response.output_item.done",
                            "output_index": text_state["output_index"],
                            "item": output_items[-1],
                        },
                    )

                # finalize tool calls
                for idx in sorted(tool_states):
                    state = tool_states[idx]
                    if state["added"]:
                        fc_item = {
                            "type": "function_call",
                            "id": state["id"],
                            "call_id": state["id"],
                            "name": state["name"],
                            "arguments": state["arguments"],
                            "status": "completed",
                        }
                        output_items.append(fc_item)
                        yield sse_event(
                            "response.output_item.done",
                            {
                                "type": "response.output_item.done",
                                "output_index": state["output_index"],
                                "item": fc_item,
                            },
                        )

                usage = translate_usage(chunk.usage)
                break

    except openai.APIError as exc:
        yield sse_event(
            "response.completed",
            {
                "type": "response.completed",
                "response": {
                    "id": response_id,
                    "object": "response",
                    "status": "incomplete",
                    "model": model,
                    "output": output_items,
                    "error": str(exc),
                },
            },
        )
        return

    yield sse_event(
        "response.completed",
        {
            "type": "response.completed",
            "response": {
                "id": response_id,
                "object": "response",
                "created_at": now_ts(),
                "status": "completed",
                "model": model,
                "output": output_items,
                "usage": usage,
            },
        },
    )


# ---------- FastAPI app ----------

app = FastAPI(title="codex-buddy-gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/models")
async def list_models():
    """Proxy the model list from the upstream CodeBuddy2api."""
    try:
        client = openai.OpenAI(base_url=CODEBUDDY_BASE_URL, api_key=CODEBUDDY_API_KEY)
        models = client.models.list()
        return {"object": "list", "data": [m.to_dict() for m in models.data]}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/v1/responses")
async def create_response(request: Request):
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    if ORCHESTRATE:
        if body.get("stream", True):
            return StreamingResponse(
                orchestrated_sse(body),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        try:
            return JSONResponse(run_orchestrated_turn(body))
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    if body.get("stream", True):
        return StreamingResponse(
            stream_events(body),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # ---- non-streaming path ----
    client = openai.OpenAI(base_url=CODEBUDDY_BASE_URL, api_key=CODEBUDDY_API_KEY)
    payload = build_chat_payload(body)
    try:
        completion = client.chat.completions.create(**payload)
    except openai.APIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    message = completion.choices[0].message
    response_id = generate_response_id()
    return JSONResponse(
        {
            "id": response_id,
            "object": "response",
            "created_at": now_ts(),
            "status": "completed",
            "model": payload["model"],
            "output": build_response_output(message),
            "usage": translate_usage(completion.usage),
        }
    )


if __name__ == "__main__":
    print(f"Starting codex-buddy-gateway on http://{GATEWAY_HOST}:{GATEWAY_PORT}")
    print(f"Upstream: {CODEBUDDY_BASE_URL}")
    uvicorn.run(app, host=GATEWAY_HOST, port=GATEWAY_PORT, log_level="info")
