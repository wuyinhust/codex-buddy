# 常见问题排查

## 1. Codex 里没有出现 CodeBuddy 模型

- 确认 `ocx start` 已运行：`ocx health` 应返回健康。
- 确认 `ocx provider list` 能看到 `codebuddy` 且为 default。
- 完全退出 Codex App（含托盘图标）后重新打开。

## 2. 选择模型后请求失败 / 401 / 403

- 确认 **CodeBuddy2api** 已启动：`curl http://127.0.0.1:8001/codebuddy/v1/models` 应返回模型列表。
- 确认 `CodeBuddy2api/.env` 里的 `CODEBUDDY_API_KEY` 已填且有效。
- 查看 CodeBuddy2api 终端日志里的具体报错。

## 3. Codex 只能聊天，不会调用工具

- 跑 README 里的 `curl` 自检命令，看 CodeBuddy2api 是否返回 `tool_calls`。
  - 无 `tool_calls` → CodeBuddy 后端/账号未开通 function calling，换模型或联系 CodeBuddy 开放平台。
  - 有 `tool_calls` → 问题在网关层，检查 `ocx` 是否正常运行。

## 4. `ocx provider add` 报错 loopback address

必须加 `--allow-private-network` 参数，因为 CodeBuddy2api 跑在本地 127.0.0.1。

## 5. 想切回 OpenAI 官方模型

```bash
ocx restore
```

## 6. 后台进程关了怎么办

CodeBuddy2api 和 `ocx start` 是前台/后台进程，关闭终端可能退出。可用 `tmux`/`screen` 常驻，或 `ocx service` 把 ocx 注册为系统服务。

## 7. 在中国大陆无法 `git push` 到 GitHub

本仓库文件通过 `gh api` Contents API 上传。如需本地 push，可配置 git 代理：

```bash
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
```

端口根据你的实际代理调整。
