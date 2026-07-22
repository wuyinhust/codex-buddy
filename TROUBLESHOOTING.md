# 常见问题排查

## 1. Codex App 里没有出现 CodeBuddy 模型

**可能原因与解决：**

- `~/.codex/config.toml` 语法错误。用 `tomlv ~/.codex/config.toml` 或在线 TOML 校验器检查。
- `model_provider` 与 `[model_providers.xxx]` 的表头不一致。确保 `model_provider = "codebuddy"` 对应 `[model_providers.codebuddy]`。
- Codex App 缓存。完全退出 Codex App（含托盘图标）后重新打开。
- 环境变量 `CODEBUDDY_PROXY_KEY` 未导出。在启动 Codex 的同一 shell/会话里执行 `export CODEBUDDY_PROXY_KEY=local`。

## 2. 选择模型后请求失败 / 返回 401 / 403

- 确认 **CodeBuddy2api** 已启动：`curl http://127.0.0.1:8001/codebuddy/v1/models` 应返回模型列表。
- 确认 `CODEBUDDY_API_KEY` 有效（或 OAuth 模式已正确获取）。查看 CodeBuddy2api 终端日志。
- 若用 **方案 B（CC Switch）**，确认 CC Switch 状态为绿色，且 Local Routing 已开启。
- 若用 **方案 A（opencodex）**，确认 `ocx start` 已运行，且 `base_url` 端口与 `ocx status` 显示一致（默认 10100）。

## 3. Codex 只能聊天，不会调用工具（不读文件、不执行命令）

- 先跑[本地自检命令](README.md#本地自检可选)，看 CodeBuddy2api 是否返回 `tool_calls`。
  - 无 `tool_calls` → CodeBuddy 后端/账号未开通 function calling，换模型或联系 CodeBuddy 开放平台。
  - 有 `tool_calls` → 问题在网关层或 Codex 配置，检查网关是否把 `tools` 参数透传给了 CodeBuddy2api。
- 确认 `wire_api = "responses"`。如果写成 `"chat"`，Codex 2026 版会报错或无法使用。

## 4. `gh repo create` / `git push` 连不上 github.com

在中国大陆网络环境下，`git push` 直连 `github.com:443` 可能被阻断。 workaround：

- 用 `gh api` 的 Contents API 上传/更新文件（本仓库 README 和 LICENSE 就是通过此方式推送的）。
- 或配置 git 走代理：

  ```bash
  git config --global http.proxy http://127.0.0.1:7890
  git config --global https.proxy http://127.0.0.1:7890
  ```

  端口根据你的实际代理调整。

## 5. CodeBuddy2api 报错或闪退

- 检查 Python 版本 ≥ 3.9。
- 检查 `.env` 文件存在且 `CODEBUDDY_API_KEY` 已填。
- 查看 `requirements.txt` 是否全部安装成功：`pip install -r requirements.txt`。
- 若在中国大陆，克隆/安装依赖可能需要配置 pip 镜像或代理。

## 6. 端到端验证失败（Codex 不执行动作）

- 给 Codex 的 prompt 必须明确要求它**执行动作**，例如：
  > "读取 README.md，把标题改成 '# Hello CodeBuddy'，然后运行 `cat README.md` 确认结果。"
- 如果 Codex 仍不动作，检查 Codex App 的 approval_policy 设置。某些模式下工具调用需要手动确认。

---

如以上都未能解决，请保留以下信息再提问：

1. 你使用的方案（A 或 B）及关键配置（去掉 API Key）。
2. CodeBuddy2api 的启动日志（前 20 行 + 请求时的错误行）。
3. Codex App / CLI 的具体报错信息。
