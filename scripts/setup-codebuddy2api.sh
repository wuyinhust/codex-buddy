#!/usr/bin/env bash
set -e

# 一键下载并启动 CodeBuddy2api（OpenAI 兼容代理）
# 用法：./scripts/setup-codebuddy2api.sh [目录名]
# 默认目录：./CodeBuddy2api

TARGET_DIR="${1:-./CodeBuddy2api}"

if [ ! -d "$TARGET_DIR" ]; then
  echo "==> 克隆 Sliverkiss/CodeBuddy2api 到 $TARGET_DIR ..."
  git clone https://github.com/Sliverkiss/CodeBuddy2api.git "$TARGET_DIR"
fi

cd "$TARGET_DIR"

echo "==> 创建 Python 虚拟环境 ..."
python3 -m venv venv
source venv/bin/activate

echo "==> 安装依赖 ..."
pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "==> 创建 .env 模板，请编辑后重新运行启动命令 ..."
  cat > .env <<'EOF'
# CodeBuddy2api 鉴权模式：api_key（推荐）或 oauth
CODEBUDDY_AUTH_MODE=api_key

# 你的 CodeBuddy 开放平台 API Key
CODEBUDDY_API_KEY=your_codebuddy_api_key_here

# 可选：显式指定模型列表，多个用逗号分隔
# CODEBUDDY_MODELS=auto-chat
EOF
  echo ""
  echo "⚠️  请编辑 $TARGET_DIR/.env，填入你的 CODEBUDDY_API_KEY，然后运行："
  echo "    cd $TARGET_DIR && source venv/bin/activate && python web.py"
  exit 0
fi

echo "==> 启动 CodeBuddy2api ..."
python web.py
