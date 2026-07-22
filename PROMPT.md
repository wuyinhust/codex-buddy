# Auto-Configure codex-buddy

Please set up codex-buddy for me: wire OpenAI Codex to Tencent CodeBuddy so I can use CodeBuddy's model catalog (Kimi K3, Hunyuan3 Hy3, DeepSeek-V4, GLM-5.2, MiniMax-M3, etc.) inside Codex.

Run the steps below in order. Report the result of each step before moving on. If a step fails, stop and ask for help.

## Pre-requisites

This machine needs `python3`, `node`, `npm`, `git`, and `curl`. Verify them first:

```bash
command -v python3 && command -v node && command -v npm && command -v git && command -v curl
```

## 1. Start CodeBuddy2api

From the repository root, run:

```bash
./scripts/setup-codebuddy2api.sh
```

- The script clones CodeBuddy2api and prepares a `.env` file.
- If it stops and asks for an API key, edit `CodeBuddy2api/.env`:
  - `CODEBUDDY_INTERNET_ENVIRONMENT=internal` for the China edition (default)
  - `CODEBUDDY_INTERNET_ENVIRONMENT=public` for the International edition
  - `CODEBUDDY_API_KEY=your_codebuddy_api_key`
- Then re-run `./scripts/setup-codebuddy2api.sh` to start the proxy.

Wait until it is healthy:

```bash
for i in {1..30}; do
  curl -s http://127.0.0.1:8001/codebuddy/v1/models >/dev/null && echo "CodeBuddy2api OK" && break
  sleep 1
done
```

## 2. Register CodeBuddy in opencodex

```bash
npm install -g @bitkyc08/opencodex

ocx provider add codebuddy \
  --adapter openai-compatible \
  --base-url http://127.0.0.1:8001/codebuddy/v1 \
  --api-key dummy \
  --allow-private-network \
  --set-default \
  --sync
```

## 3. Start the gateway

```bash
ocx start
```

Check health:

```bash
ocx health
```

## 4. Verify tool calling

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

## 5. Report completion

Tell me the setup is done and list the running background processes (CodeBuddy2api and opencodex) with their PIDs.

If I later want to switch back to the official OpenAI model, run:

```bash
ocx restore
```
