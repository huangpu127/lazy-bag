#!/bin/bash
# 懒人包 Railway 部署脚本

echo "=== 懒人包 Railway 部署 ==="
echo ""

# 检查是否安装了 Railway CLI
if ! command -v railway &> /dev/null; then
    echo "正在安装 Railway CLI..."
    npm install -g @railway/cli
fi

# 登录 Railway
echo "使用 Token 登录 Railway..."
railway login --token 91a17276-7b1b-4648-9b10-fb02ce277a68

# 进入后端目录
cd ~/lazy-bag-project/lazy-bag-backend

# 初始化项目
echo ""
echo "初始化 Railway 项目..."
railway init

# 添加环境变量
echo ""
echo "配置环境变量..."
echo "请输入你的 API 密钥（如果没有可以直接回车跳过，后续在网页上配置）："

read -p "TAVILY_API_KEY: " TAVILY_KEY
if [ ! -z "$TAVILY_KEY" ]; then
    railway variables set TAVILY_API_KEY="$TAVILY_KEY"
fi

read -p "OPENROUTER_API_KEY: " OPENROUTER_KEY
if [ ! -z "$OPENROUTER_KEY" ]; then
    railway variables set OPENROUTER_API_KEY="$OPENROUTER_KEY"
fi

read -p "SERP_API_KEY (可选): " SERP_KEY
if [ ! -z "$SERP_KEY" ]; then
    railway variables set SERP_API_KEY="$SERP_KEY"
fi

# 部署
echo ""
echo "开始部署..."
railway up

echo ""
echo "=== 部署完成 ==="
echo "访问 Railway 控制台查看部署状态: https://railway.app/dashboard"
