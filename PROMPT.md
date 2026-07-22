# 自动配置 codex-buddy

请按以下步骤帮我把 Codex 接入 CodeBuddy。每完成一步后向我汇报结果；遇到错误立即停止并说明原因。

## 目标

让 Codex（App / CLI）通过本地代理使用 CodeBuddy 模型驱动 agent 循环（读文件、改代码、执行命令）。

## 网络与鉴权前提

- 本机需要能访问 npm、GitHub、CodeBuddy 官方 API。
- 你需要一个 CodeBuddy 开放平台 API Key。如果环境变量 `CODEBUDDY_API_KEY` 未设置，请在第一步时向我询问。

## 执行步骤

### 1. 检查环境

确认已安装：

```bash
command -v python3 && command -v node && command -v npm && command -v git && command -v curl
```

### 2. 启动 CodeBuddy2api

在仓库根目录执行：

```bash
./scripts/setup-codebuddy2api.sh
```

- 如果脚本提示你填写 `.env` 文件，请在 `CodeBuddy2api/.env` 中写入：
  ```
  CODEBUDDY_AUTH_MODE=api_key
  CODEBUDDY_API_KEY=你的CodeBuddy_API_Key
  ```
  然后再次运行 `./scripts/setup-codebuddy2api.sh`。
- 脚本启动后会在后台运行 CodeBuddy2api，监听 `127.0.0.1:8001`。

验证是否健康：

```bash
for i in {1..30}; do
  curl -s http://127.0.0.1:8001/codebuddy/v1/models >/dev/null && echo "CodeBuddy2api OK" && break
  sleep 1
done
```

### 3. 安装并配置 opencodex

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

### 4. 启动 opencodex 网关

```bash
ocx start
```

验证网关健康：

```bash
ocx health
```

### 5. 验证工具调用链

```bash
curl http://127.0.0.1:8001/codebuddy/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"auto-chat",
    "messages":[{"role":"user","content":"用计算器算 1+1"}],
    "tools":[{"type":"function","function":{"name":"calc","description":"计算","parameters":{"type":"object","properties":{"expr":{"type":"string"}}}}}],
    "tool_choice":"auto"
  }'
```

确认返回里包含 `"tool_calls"`。如果没有，说明当前 CodeBuddy 账号/模型未开通 function calling，需要换模型或联系 CodeBuddy 开放平台。

### 6. 完成

告诉我配置已完成，并列出后台运行的进程（CodeBuddy2api 和 ocx）及其 PID，方便我后续管理。

## 还原方法

如果我想切回 OpenAI 官方模型，请执行：

```bash
ocx restore
```

## 注意事项

- `ocx sync` 会修改 `~/.codex/config.toml`，把模型目录指向 opencodex 代理。`ocx restore` 可撤销。
- CodeBuddy2api 和 ocx 是两个后台进程；关闭终端后可能退出，必要时可用 `tmux` 或 `ocx service` 常驻。
