#!/bin/bash
# 启动 4D-Humans MoCap API 服务

set -e

# 切换到项目目录
cd "$(dirname "$0")/.."

# 激活 Conda 环境（如果使用）
# source /path/to/conda/etc/profile.d/conda.sh
# conda activate 4d-humans

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please copy deploy/env.example to .env and configure it."
    exit 1
fi

# 创建必要的目录
mkdir -p uploads results outputs tmp logs

# 启动服务
echo "🚀 Starting 4D-Humans MoCap API..."
python -m api.main

