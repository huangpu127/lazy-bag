# 懒人包插件部署指南

## 概述

懒人包插件包含两部分：
1. **后端服务** (FastAPI) - 处理搜索和 AI 生成
2. **Chrome 扩展** - 前端交互界面

## 部署方案：Railway 免费托管（推荐试用）

### 第一步：准备 API 密钥

在部署前，你需要准备以下 API 密钥：

1. **Tavily API Key**（首选搜索服务）
   - 注册地址：https://tavily.com/
   - 免费额度：每月 1000 次调用

2. **SerpAPI Key**（备用搜索服务）
   - 注册地址：https://serpapi.com/
   - 免费额度：每月 100 次调用

3. **Anthropic Claude API Key**（AI 生成首选）
   - 注册地址：https://console.anthropic.com/
   - 或使用 OpenRouter 作为替代

4. **OpenRouter API Key**（AI 生成备用）
   - 注册地址：https://openrouter.ai/
   - 优点：支持多种模型，部分模型免费

### 第二步：部署后端到 Railway

#### 方法 A：通过 Railway 网页界面部署（推荐）

1. **Fork 或下载代码**
   ```bash
   # 确保你有一个 GitHub 仓库包含以下文件：
   # - main.py
   # - requirements.txt
   # - Procfile
   # - runtime.txt
   ```

2. **登录 Railway**
   - 访问 https://railway.app/
   - 使用 GitHub 账号登录

3. **创建新项目**
   - 点击 "New Project"
   - 选择 "Deploy from GitHub repo"
   - 选择你的代码仓库

4. **配置环境变量**
   - 进入项目 Settings → Variables
   - 添加以下环境变量：

   ```
   TAVILY_API_KEY=your_tavily_api_key
   SERP_API_KEY=your_serpapi_key
   ANTHROPIC_API_KEY=your_anthropic_key
   OPENROUTER_API_KEY=your_openrouter_key
   ALLOWED_ORIGINS=*
   ```

5. **部署**
   - Railway 会自动检测 Procfile 并部署
   - 等待部署完成（约 2-3 分钟）

6. **获取域名**
   - 部署完成后，Railway 会分配一个域名
   - 格式如：`https://lazy-bag-api.up.railway.app`
   - 复制这个域名，后续配置扩展时需要

#### 方法 B：通过 Railway CLI 部署

```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录
railway login

# 进入后端目录
cd lazy-bag-backend

# 初始化项目
railway init

# 设置环境变量
railway variables set TAVILY_API_KEY=your_key
railway variables set SERP_API_KEY=your_key
railway variables set ANTHROPIC_API_KEY=your_key
railway variables set OPENROUTER_API_KEY=your_key

# 部署
railway up
```

### 第三步：验证后端部署

部署完成后，测试后端是否正常工作：

```bash
# 替换为你的 Railway 域名
API_URL="https://your-app.up.railway.app"

# 测试健康检查
curl $API_URL/health

# 测试解释 API
curl -X POST $API_URL/api/explain \
  -H "Content-Type: application/json" \
  -d '{"query": "马斯克"}'
```

### 第四步：打包 Chrome 扩展

1. **进入扩展目录**
   ```bash
   cd lazy-bag
   ```

2. **修改默认 API 地址（可选）**
   - 编辑 `options.js`
   - 将 `DEFAULT_API_URL` 改为你的 Railway 域名

3. **打包扩展**
   ```bash
   # 创建扩展包
   zip -r lazy-bag-extension.zip . -x "*.git*"
   ```

   或者直接压缩文件夹：
   - 右键 `lazy-bag` 文件夹
   - 选择"压缩"
   - 重命名为 `lazy-bag-extension.zip`

### 第五步：分享给他人使用

#### 方式 1：开发者模式安装（适合小范围分享）

1. 将 `lazy-bag-extension.zip` 发送给使用者
2. 使用者解压文件
3. 打开 Chrome 扩展管理页：`chrome://extensions/`
4. 开启"开发者模式"
5. 点击"加载已解压的扩展程序"
6. 选择解压后的 `lazy-bag` 文件夹
7. 点击扩展图标，配置后端 API 地址

#### 方式 2：Chrome Web Store 上架（适合大范围分发）

1. 注册 Chrome Web Store 开发者账号
   - 费用：$5 一次性
   - 地址：https://chrome.google.com/webstore/devconsole

2. 打包扩展
   ```bash
   # 使用 Chrome 提供的工具打包
   # 或直接 zip 压缩（注意：不要包含 _metadata 文件夹）
   ```

3. 上传并提交审核
   - 通常审核需要 1-3 天

## 部署方案：Render 免费托管（备选）

如果 Railway 的免费额度用完，可以使用 Render：

1. 访问 https://render.com/
2. 创建 Web Service
3. 连接 GitHub 仓库
4. 配置：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. 添加相同的环境变量
6. 部署

## 故障排查

### 后端无法启动

```bash
# 查看日志
railway logs

# 常见问题：
# 1. 缺少环境变量 - 检查 Variables 设置
# 2. 依赖安装失败 - 检查 requirements.txt 格式
# 3. 端口冲突 - 确保使用 $PORT 环境变量
```

### 扩展无法连接后端

1. **检查 API 地址配置**
   - 点击扩展图标
   - 确认地址格式正确（以 https:// 开头，无末尾斜杠）

2. **检查 CORS 设置**
   - 确保 `ALLOWED_ORIGINS=*` 或包含 `chrome-extension://*`

3. **检查网络**
   - 在扩展页面打开开发者工具
   - 查看 Network 面板的请求错误

### API 限额问题

- **Tavily**: 免费 1000 次/月
- **SerpAPI**: 免费 100 次/月
- **Claude**: 按 token 计费，新用户有免费额度

建议：
1. 监控使用量
2. 设置缓存（已内置 24 小时缓存）
3. 必要时升级付费计划

## 安全建议

1. **不要提交 API 密钥到 GitHub**
   - 使用环境变量
   - 添加 `.env` 到 `.gitignore`

2. **限制 CORS 域名（生产环境）**
   ```
   ALLOWED_ORIGINS=https://your-extension-id.chromiumapp.org
   ```

3. **添加请求限流**（可选）
   - 使用 Redis 或内存限流
   - 防止 API 额度被滥用

## 成本估算

### 免费方案
- Railway/Render: $0（有冷启动）
- Tavily: $0（1000 次/月）
- SerpAPI: $0（100 次/月，备用）
- OpenRouter: $0（使用免费模型）
- **总计：$0/月**

### 低成本方案（如需更高稳定性）
- Railway Hobby: $5/月（无冷启动）
- Tavily Pro: $0（1000 次免费额度通常足够）
- **总计：约 $5/月**

## 更新维护

### 更新后端

```bash
# 修改代码后重新部署
git push origin main
# Railway 会自动重新部署
```

### 更新扩展

1. 修改版本号（manifest.json）
2. 重新打包
3. 发送给使用者重新安装
4. （如上架 Web Store）上传新版本

## 获取帮助

如有问题，请检查：
1. Railway 部署日志
2. Chrome 扩展开发者工具（Console 和 Network）
3. 后端 `/health` 接口返回状态
