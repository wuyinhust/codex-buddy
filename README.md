# codex-buddy

Use CodeBuddy-compatible models from Codex through a local Responses API gateway.
In orchestration mode, GPT plans and reviews while CodeBuddy models execute the work.

```text
Codex conversation
  → codex-buddy-gateway
  → GPT plan
  → CodeBuddy worker models
  → GPT review
  → one answer returned to Codex
```

## What is included

- `codex-buddy-gateway.py`: `/v1/responses` to Chat Completions bridge.
- `gpt-kimi-orchestrator.py`: GPT planner/reviewer with CodeBuddy workers.
- `test_gateway_dryrun.py`: offline gateway test using a mock upstream.
- `scripts/setup-codebuddy2api.sh`: prepares the external CodeBuddy2api dependency.

The gateway does not change Codex login files. Do not use tools that rewrite Codex configuration if preserving the official login is important.

## Setup

The gateway expects a running CodeBuddy2api-compatible endpoint at:

```text
http://127.0.0.1:8001/codebuddy/v1
```

Prepare that separate dependency with the bundled script when you are ready to run it:

```bash
./scripts/setup-codebuddy2api.sh
```

Configure its `.env` with your CodeBuddy API key and, if needed, the edition setting. This repository does not contain CodeBuddy credentials.

Install gateway dependencies:

```bash
pip install -r requirements.txt
```

## Direct gateway mode

Start only after the required upstream is ready:

```bash
python codex-buddy-gateway.py
```

The gateway listens on:

```text
http://127.0.0.1:8787/v1
```

Point a separate Codex API-base/profile at this URL using Responses mode. The requested model name is forwarded to CodeBuddy2api.

Useful variables:

```bash
export CODEBUDDY_BASE_URL="http://127.0.0.1:8001/codebuddy/v1"
export CODEBUDDY_API_KEY="dummy"
export CODEBUDDY_MODEL="kimi-k3"
export GATEWAY_HOST="127.0.0.1"
export GATEWAY_PORT="8787"
```

## GPT orchestration mode

Set these variables before starting the gateway:

```bash
export CODEBUDDY_ORCHESTRATE=1
export ORCHESTRATOR_API_KEY="your OpenAI API key"
export ORCHESTRATOR_MODEL="gpt-4o-mini"
export WORKER_BASE_URLS="http://127.0.0.1:8001/codebuddy/v1"
export WORKER_DEFAULT_MODEL="kimi-k3"
export WORKER_FALLBACK_MODEL="hy3-high"
```

Each request is handled as one turn: GPT receives the current conversation, creates subtasks, CodeBuddy workers execute them, and GPT returns the final response. The mode is opt-in; without `CODEBUDDY_ORCHESTRATE=1`, the gateway only translates the request.

## Verify without starting services

```bash
python3 test_gateway_dryrun.py
```

For a live setup, the upstream and gateway must both be running. This README does not claim that either service is running.

## License

[MIT](LICENSE)
