#!/usr/bin/env python3
"""
GPT-Kimi Orchestrator
=====================
A lightweight supervisor-worker loop: GPT plans, Kimi (via CodeBuddy) executes,
and GPT reviews the results.

Run:
    python gpt-kimi-orchestrator.py "帮我写一个 Python 脚本，把 Markdown 转成 PDF"

Environment variables (or a `.env` file):
    OPENAI_API_KEY              # API key for the orchestrator (GPT)
    ORCHESTRATOR_BASE_URL       # default: https://api.openai.com/v1
    ORCHESTRATOR_MODEL          # default: gpt-4o-mini
    WORKER_BASE_URLS            # comma-separated CodeBuddy2api endpoints
    WORKER_API_KEYS             # comma-separated API keys for those endpoints (often "dummy")
    WORKER_ACCOUNT_NAMES        # optional human-readable names for endpoints
    WORKER_DEFAULT_MODEL        # default: kimi-k3
    WORKER_FALLBACK_MODEL       # default: hy3-high
"""

import os
import sys
import json
import argparse
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv
import openai

load_dotenv()


@dataclass
class Account:
    base_url: str
    api_key: str
    name: str
    exhausted: bool = False
    usage_prompt: int = 0
    usage_completion: int = 0


@dataclass
class UsageBucket:
    prompt: int = 0
    completion: int = 0

    def add(self, usage: Optional[Any]) -> None:
        if usage is None:
            return
        self.prompt += getattr(usage, "prompt_tokens", 0)
        self.completion += getattr(usage, "completion_tokens", 0)

    @property
    def total(self) -> int:
        return self.prompt + self.completion

    def __str__(self) -> str:
        return f"{self.prompt} prompt / {self.completion} completion / {self.total} total"


class Orchestrator:
    def __init__(self) -> None:
        orchestrator_key = os.getenv("ORCHESTRATOR_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not orchestrator_key:
            raise RuntimeError(
                "Missing OPENAI_API_KEY (or ORCHESTRATOR_API_KEY). "
                "Set it in the environment or a .env file."
            )

        self.orchestrator_client = openai.OpenAI(
            base_url=os.getenv("ORCHESTRATOR_BASE_URL", "https://api.openai.com/v1"),
            api_key=orchestrator_key,
        )
        self.orchestrator_model = os.getenv("ORCHESTRATOR_MODEL", "gpt-4o-mini")

        self.worker_accounts = self._load_worker_accounts()
        if not self.worker_accounts:
            raise RuntimeError("No worker endpoints configured. Set WORKER_BASE_URLS.")

        self.default_worker_model = os.getenv("WORKER_DEFAULT_MODEL", "kimi-k3")
        self.fallback_worker_model = os.getenv("WORKER_FALLBACK_MODEL", "hy3-high")
        self.usage = {"orchestrator": UsageBucket(), "worker": UsageBucket()}
        self.task_results: Dict[str, str] = {}

    def _load_worker_accounts(self) -> List[Account]:
        endpoints = [u.strip() for u in os.getenv("WORKER_BASE_URLS", "http://127.0.0.1:8001/codebuddy/v1").split(",")]
        keys = [k.strip() if k.strip() else "dummy" for k in os.getenv("WORKER_API_KEYS", "dummy").split(",")]
        names = [n.strip() for n in os.getenv("WORKER_ACCOUNT_NAMES", "").split(",")]

        accounts: List[Account] = []
        for i, url in enumerate(endpoints):
            if not url:
                continue
            key = keys[i] if i < len(keys) else keys[-1]
            name = names[i] if i < len(names) and names[i] else f"account-{i + 1}"
            accounts.append(Account(base_url=url, api_key=key, name=name))
        return accounts

    def plan(self, task: str) -> List[Dict[str, Any]]:
        """Ask GPT to break the task into sub-tasks and assign a model to each."""
        system_prompt = (
            "You are a task planner. Given a user request, break it into a list of "
            "concrete sub-tasks. For each sub-task, choose the most suitable model from "
            "CodeBuddy's catalog: kimi-k3 (coding/Chinese), hy3-high (reasoning, "
            "limited-time free), auto-chat (general). Return ONLY a JSON object with "
            "a single key 'tasks' containing an array of objects with fields: "
            "id (string), description (string), model (string), depends_on (list of ids)."
        )
        response = self.orchestrator_client.chat.completions.create(
            model=self.orchestrator_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ],
            response_format={"type": "json_object"},
        )
        self.usage["orchestrator"].add(response.usage)

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Planner returned empty content")
        data = json.loads(content)
        tasks = data.get("tasks") if isinstance(data, dict) else data
        if not isinstance(tasks, list):
            raise RuntimeError(f"Planner returned unexpected shape: {data}")
        return tasks

    def execute(self, tasks: List[Dict[str, Any]]) -> None:
        """Execute tasks in dependency order."""
        completed = set()
        while len(completed) < len(tasks):
            progressed = False
            for task in tasks:
                tid = task["id"]
                if tid in completed:
                    continue
                deps = task.get("depends_on", [])
                if all(d in completed for d in deps):
                    result = self._delegate(task)
                    self.task_results[tid] = result
                    completed.add(tid)
                    progressed = True
                    break
            if not progressed:
                raise RuntimeError("Cannot resolve task dependencies (possible cycle or missing dependency)")

    def _delegate(self, task: Dict[str, Any]) -> str:
        model = task.get("model") or self.default_worker_model
        prompt = self._build_task_prompt(task)
        messages = [
            {
                "role": "system",
                "content": "You are a helpful coding assistant. Complete the task concisely and return only the requested output.",
            },
            {"role": "user", "content": prompt},
        ]
        return self._call_worker(model, messages)

    def _build_task_prompt(self, task: Dict[str, Any]) -> str:
        parts = [f"Task: {task['description']}"]
        for dep in task.get("depends_on", []):
            dep_result = self.task_results.get(dep, "")
            parts.append(f"\n[Context from previous step '{dep}']:\n{dep_result}")
        return "\n".join(parts)

    def _call_worker(self, model: str, messages: List[Dict[str, str]]) -> str:
        """Try worker accounts one by one, then fallback to a cheaper/free model."""
        candidates = [a for a in self.worker_accounts if not a.exhausted] or self.worker_accounts
        last_error: Optional[Exception] = None

        for account in candidates:
            try:
                client = openai.OpenAI(base_url=account.base_url, api_key=account.api_key)
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=4096,
                )
                self.usage["worker"].add(response.usage)
                if response.usage:
                    account.usage_prompt += response.usage.prompt_tokens
                    account.usage_completion += response.usage.completion_tokens
                content = response.choices[0].message.content
                return content or ""
            except openai.RateLimitError as e:
                last_error = e
                account.exhausted = True
                print(f"[worker] Account '{account.name}' rate-limited. Switching...", file=sys.stderr)
            except openai.APIStatusError as e:
                last_error = e
                if self._is_quota_error(e):
                    account.exhausted = True
                    print(f"[worker] Account '{account.name}' out of quota ({e.status_code}). Switching...", file=sys.stderr)
                else:
                    raise
            except openai.APIError as e:
                last_error = e
                print(f"[worker] Account '{account.name}' API error: {e}. Switching...", file=sys.stderr)
                continue

        # If every account failed for the requested model, try the fallback model once.
        if model != self.fallback_worker_model:
            print(
                f"[worker] All accounts failed for '{model}'. Falling back to '{self.fallback_worker_model}'...",
                file=sys.stderr,
            )
            return self._call_worker(self.fallback_worker_model, messages)

        raise RuntimeError(f"All worker accounts exhausted and fallback failed. Last error: {last_error}")

    @staticmethod
    def _is_quota_error(e: openai.APIStatusError) -> bool:
        if e.status_code == 429:
            return True
        if e.status_code == 403 and e.response is not None:
            body = getattr(e.response, "text", "") or ""
            lowered = body.lower()
            if any(word in lowered for word in ("quota", "insufficient", "balance", "limit")):
                return True
        return False

    def review(self, original_task: str) -> str:
        """Synthesize all sub-task outputs into a final answer."""
        results = json.dumps(self.task_results, ensure_ascii=False, indent=2)
        system_prompt = (
            "You are a synthesis reviewer. Combine the sub-task results below into a "
            "clear, complete final answer to the user's original request. Do not add "
            "unsubstantiated claims."
        )
        response = self.orchestrator_client.chat.completions.create(
            model=self.orchestrator_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Original request: {original_task}\n\nSub-task results:\n{results}",
                },
            ],
        )
        self.usage["orchestrator"].add(response.usage)
        return response.choices[0].message.content or ""

    def print_usage(self) -> None:
        print("\n--- Token Usage ---")
        for account in self.worker_accounts:
            print(
                f"  {account.name}: {account.usage_prompt} prompt / "
                f"{account.usage_completion} completion"
            )
        print(f"Orchestrator: {self.usage['orchestrator']}")
        print(f"Worker      : {self.usage['worker']}")
        print(f"Grand total : {self.usage['orchestrator'].total + self.usage['worker'].total}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GPT-Kimi Orchestrator: plan, delegate, review."
    )
    parser.add_argument("task", help="The task / prompt you want to solve.")
    args = parser.parse_args()

    orchestrator = Orchestrator()

    print(f"[orchestrator] Planning task: {args.task}")
    tasks = orchestrator.plan(args.task)
    print(f"[orchestrator] Plan:\n{json.dumps(tasks, ensure_ascii=False, indent=2)}")

    print("[orchestrator] Delegating to worker models...")
    orchestrator.execute(tasks)

    print("[orchestrator] Reviewing and synthesizing...")
    final_answer = orchestrator.review(args.task)

    print("\n=== Final Answer ===\n")
    print(final_answer)

    orchestrator.print_usage()


if __name__ == "__main__":
    main()
