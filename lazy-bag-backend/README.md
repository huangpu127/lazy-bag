# 懒人包 (Lazy Bag)

> 选中网页关键词，一键获取基于可靠信源的 AI 解释

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/placeholder)

## 功能特性

- 🔍 **智能搜索** - 自动搜索 Tavily + SerpAPI 双保险
- 🤖 **AI 总结** - 基于搜索结果生成，避免幻觉
- 📰 **权威信源** - 优先引用 Reuters、BBC、财新等权威媒体
- ⚡ **快速响应** - 24小时缓存，常用查询秒开
- 🔒 **隐私保护** - 不存储用户查询历史

## 项目结构

```
lazy-bag/
├── lazy-bag/               # Chrome 扩展（前端）
│   ├── manifest.json       # 扩展配置
│   ├── background.js       # 后台脚本
│   ├── content.js          # 内容脚本
│   ├── options.html        # 设置页面
│   └── styles.css          # 样式
│
└── lazy-bag-backend/       # FastAPI 后端
    ├── main.py             # 主程序
    ├── requirements.txt    # Python 依赖
    ├── Procfile            # Railway 部署配置
    ├── runtime.txt         # Python 版本
    └── DEPLOY.md           # 详细部署文档
```

## 快速开始

### 1. 部署后端（免费）

#### 使用 Railway（推荐）

1. **Fork 本仓库**

2. **注册 API 密钥**
   - [Tavily](https://tavily.com/) - 搜索服务（免费 1000次/月）
   - [OpenRouter](https://openrouter.ai/) - AI 生成（部分模型免费）

3. **部署到 Railway**
   ```
   1. 登录 https://railway.app/
   2. New Project → Deploy from GitHub repo
   3. 选择本仓库的 lazy-bag-backend 目录
   4. 添加环境变量（见下方）
   5. 部署完成，复制域名
   ```

4. **环境变量配置**
   ```env
   TAVILY_API_KEY=your_tavily_key
   SERP_API_KEY=your_serpapi_key      # 可选，备用搜索
   ANTHROPIC_API_KEY=your_claude_key  # 可选
   OPENROUTER_API_KEY=your_openrouter_key
   ALLOWED_ORIGINS=*
   ```

### 2. 安装扩展

1. 下载 `lazy-bag-extension.zip`
2. 解压文件
3. 打开 Chrome：`chrome://extensions/`
4. 开启"开发者模式"
5. 点击"加载已解压的扩展程序"
6. 选择解压后的 `lazy-bag` 文件夹
7. 点击扩展图标，配置后端地址

### 3. 开始使用

选中任意网页文字，点击 📦 按钮即可查看解释。

## API 使用

### 获取解释

```bash
curl -X POST https://your-api.up.railway.app/api/explain \
  -H "Content-Type: application/json" \
  -d '{"query": "马斯克"}'
```

响应：
```json
{
  "explanation": "埃隆·马斯克是特斯拉和 SpaceX 的创始人，致力于电动汽车和太空探索技术...",
  "sources": [
    {
      "title": "Reuters：Elon Musk biography",
      "url": "https://reuters.com/..."
    }
  ]
}
```

### 健康检查

```bash
curl https://your-api.up.railway.app/health
```

## 技术栈

- **后端**: FastAPI + Python 3.11
- **搜索**: Tavily API + SerpAPI
- **AI**: Claude (Anthropic) / DeepSeek (OpenRouter)
- **前端**: Chrome Extension (Manifest V3)

## 信源分级

系统按以下优先级排序搜索结果：

| 级别 | 类型 | 示例 |
|------|------|------|
| T0 | 百科词条 | Wikipedia、Investopedia |
| T1 | 官方机构 | 政府网站、央行、WHO |
| T2 | 主流媒体 | Reuters、BBC、财新、FT |
| T3 | 自媒体 | 知乎、微信公众号 |

财经/政治类查询会优先展示财新等权威媒体来源。

## 成本估算

### 免费方案
- Railway: $0（有冷启动）
- Tavily: $0（1000次/月）
- OpenRouter: $0（免费模型）
- **总计：$0/月**

### 低成本方案
- Railway Hobby: $5/月（无冷启动）
- API 调用: $0（免费额度通常足够）
- **总计：约 $5/月**

## 开发

### 本地运行后端

```bash
cd lazy-bag-backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API 密钥

# 启动服务
python main.py
```

服务运行在 http://localhost:8001

### 本地运行扩展

1. 修改 `lazy-bag/options.js` 中的 `DEFAULT_API_URL` 为 `http://localhost:8001`
2. Chrome 加载已解压的扩展程序
3. 选中文字测试

## 部署文档

- [详细部署指南](./DEPLOY.md)
- [5分钟快速开始](./QUICKSTART.md)

## 贡献

欢迎提交 Issue 和 PR！

## License

MIT License

---

<p align="center">Made with ❤️ for lazy readers</p>
