# 懒人包插件 - 快速部署指南

## 5 分钟快速部署

### 1. 准备 API 密钥（2分钟）

访问以下网站注册并获取 API Key：

| 服务 | 注册地址 | 用途 | 免费额度 |
|------|---------|------|---------|
| Tavily | https://tavily.com/ | 搜索 | 1000次/月 |
| SerpAPI | https://serpapi.com/ | 备用搜索 | 100次/月 |
| OpenRouter | https://openrouter.ai/ | AI生成 | 部分模型免费 |

**最少需要**：Tavily + OpenRouter 即可运行

### 2. 部署到 Railway（2分钟）

#### 步骤：

1. **Fork 本仓库到自己的 GitHub**（或创建新仓库上传代码）

2. **登录 Railway**
   - 访问 https://railway.app/
   - 用 GitHub 登录

3. **创建项目**
   ```
   New Project → Deploy from GitHub repo → 选择你的仓库
   ```

4. **添加环境变量**
   ```
   Settings → Variables → New Variable
   ```
   添加：
   - `TAVILY_API_KEY` = 你的tavily密钥
   - `SERP_API_KEY` = 你的serpapi密钥（可选）
   - `ANTHROPIC_API_KEY` = 你的claude密钥（可选）
   - `OPENROUTER_API_KEY` = 你的openrouter密钥
   - `ALLOWED_ORIGINS` = `*`

5. **获取域名**
   - 部署完成后，点击项目查看域名
   - 如：`https://lazy-bag-api.up.railway.app`

### 3. 配置扩展（1分钟）

1. **解压扩展文件**
   ```bash
   unzip lazy-bag-extension.zip
   ```

2. **安装扩展**
   - 打开 Chrome：`chrome://extensions/`
   - 开启"开发者模式"
   - 点击"加载已解压的扩展程序"
   - 选择 `lazy-bag` 文件夹

3. **配置后端地址**
   - 点击扩展图标
   - 输入 Railway 域名（如 `https://lazy-bag-api.up.railway.app`）
   - 点击保存

### 4. 开始使用！

选中任意网页文字，点击 📦 按钮即可查看懒人包解释。

---

## 一键测试命令

```bash
# 测试后端是否正常工作
API_URL="https://你的域名.up.railway.app"

curl -X POST $API_URL/api/explain \
  -H "Content-Type: application/json" \
  -d '{"query": "马斯克"}'
```

---

## 常见问题

### Q: Railway 部署失败？
A: 检查 `requirements.txt` 和 `Procfile` 是否存在，且格式正确。

### Q: 扩展显示连接失败？
A: 检查 API 地址是否正确（以 https:// 开头，无末尾斜杠）

### Q: 返回结果很慢？
A: Railway 免费版有冷启动，首次请求可能需要 10-30 秒，后续正常。

### Q: API 限额用完？
A: Tavily 每月 1000 次通常足够个人使用。如需更多，可升级付费计划或使用 SerpAPI 作为备用。

---

## 文件清单

确保以下文件已上传到 GitHub：

```
lazy-bag-backend/
├── main.py              # 主程序
├── requirements.txt     # Python 依赖
├── Procfile            # Railway 启动配置
├── runtime.txt         # Python 版本
└── .env.example        # 环境变量示例
```

---

## 下一步

- 完整部署文档：查看 [DEPLOY.md](./DEPLOY.md)
- 自定义开发：修改 `main.py` 调整 AI 提示词
- 添加更多信源：编辑源代码中的 `SOURCE_TIERS`

---

**需要帮助？** 检查 Railway 日志或 Chrome 扩展开发者工具（F12 → Console）查看错误信息。
