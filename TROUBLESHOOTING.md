# Troubleshooting

## 1. No CodeBuddy model appears in Codex

- Make sure `ocx start` is running: `ocx health` should report healthy.
- Make sure `ocx provider list` shows `codebuddy` and it is marked as default.
- Fully quit Codex App (including the tray icon) and reopen it.
- Run `ocx sync` to refresh the model catalog.

## 2. Requests fail with 401 / 403

- Confirm CodeBuddy2api is running: `curl http://127.0.0.1:8001/codebuddy/v1/models`.
- Confirm `CodeBuddy2api/.env` has a valid `CODEBUDDY_API_KEY`.
- Confirm `CODEBUDDY_INTERNET_ENVIRONMENT` matches your account edition:
  - `internal` or `ioa` → China edition (`copilot.tencent.com`)
  - `public` → International edition (`www.codebuddy.ai`)
- Read the CodeBuddy2api terminal log for the exact error.

## 3. Codex only chats, does not call tools

- Run the verification curl in the README/PROMPT and check for `"tool_calls"`.
  - No `"tool_calls"` → your CodeBuddy account/model does not have function calling enabled. Try another model or contact CodeBuddy support.
  - Has `"tool_calls"` → check that `ocx` is forwarding tools correctly; restart with `ocx stop && ocx start`.

## 4. `ocx provider add` rejects the base URL

You must include `--allow-private-network` because CodeBuddy2api runs on `127.0.0.1`.

## 5. China edition vs International edition

| Edition | `CODEBUDDY_INTERNET_ENVIRONMENT` | Domain | Typical models |
|---------|----------------------------------|--------|----------------|
| China | `internal` (default) | `copilot.tencent.com` | Kimi, Hunyuan, DeepSeek, GLM, MiniMax |
| International | `public` | `www.codebuddy.ai` | GPT-5, Claude-4, Gemini-2.5 |

If you set the wrong edition, CodeBuddy2api will talk to the wrong backend and authentication will fail.

## 6. Background processes stop after closing the terminal

CodeBuddy2api and `ocx start` are tied to the terminal session by default. To keep them running:

```bash
ocx service install
ocx service start
```

For CodeBuddy2api, run it inside `tmux`/`screen` or use your OS service manager.

## 7. Switch back to OpenAI

```bash
ocx restore
```

## 8. Cannot push to GitHub from mainland China

`git push` to `github.com:443` may be blocked. Use the `gh api` Contents API instead, or configure a proxy:

```bash
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
```
