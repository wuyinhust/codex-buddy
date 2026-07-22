# Configure codex-buddy safely

Configure the local codex-buddy gateway so GPT can plan and review while Kimi/Hy3 and other CodeBuddy models execute sub-tasks in the same request.

Do not install or run `opencodex`, `ocx start`, `ocx restore`, or any command that rewrites Codex configuration or login state. Do not start services without explicit user approval.

## Pre-requisites

This machine needs `python3`, `node`, `npm`, `git`, and `curl`. Verify them first:

```bash
command -v python3 && command -v node && command -v npm && command -v git && command -v curl
```

## 1. Prepare CodeBuddy2api

From the repository root, inspect the script. Do not execute it or start CodeBuddy2api automatically:

```bash
sed -n '1,220p' scripts/setup-codebuddy2api.sh
```

If the user later explicitly approves setup, configure the separate CodeBuddy2api
environment with `CODEBUDDY_INTERNET_ENVIRONMENT` and `CODEBUDDY_API_KEY`; do not
modify Codex configuration.

## 2. Configure the orchestrated gateway

```bash
export CODEBUDDY_ORCHESTRATE=1
export ORCHESTRATOR_API_KEY="your_openai_api_key"
export ORCHESTRATOR_MODEL="gpt-4o-mini"
export WORKER_BASE_URLS="http://127.0.0.1:8001/codebuddy/v1"
export WORKER_DEFAULT_MODEL="kimi-k3"
export WORKER_FALLBACK_MODEL="hy3-high"
```

When the user explicitly approves service startup, run the bundled gateway only:

```bash
python codex-buddy-gateway.py
```

## 3. Verify tool calling

Run this curl and confirm the response contains `"tool_calls"`:

```bash
curl http://127.0.0.1:8001/codebuddy/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"auto-chat",
    "messages":[{"role":"user","content":"calculate 1+1 with the calc tool"}],
    "tools":[{"type":"function","function":{"name":"calc","description":"calculate","parameters":{"type":"object","properties":{"expr":{"type":"string"}}}}}],
    "tool_choice":"auto"
  }'
```

## 4. Report completion

Report configuration only. Do not claim that a service is running unless the user explicitly approved startup and it was actually started.
