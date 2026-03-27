"""
懒人包后端服务
提供关键词解释 API - 使用 SerpAPI/Tavily 搜索 + Claude AI 总结
"""

import os
import json
import requests
import hashlib
import time
import asyncio
import aiohttp
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from anthropic import Anthropic
from functools import lru_cache
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = FastAPI(title="懒人包 API")

# 配置 CORS - 允许 Chrome 扩展和所有部署域名访问
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "*"  # 默认允许所有来源，生产环境建议设置具体域名
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 简单的内存缓存（query_hash -> (result, timestamp)）
_response_cache = {}
CACHE_TTL = 86400  # 缓存24小时

def get_cached_response(query: str):
    """获取缓存的响应"""
    key = hashlib.md5(query.encode()).hexdigest()
    if key in _response_cache:
        result, ts = _response_cache[key]
        if time.time() - ts < CACHE_TTL:
            return result
        del _response_cache[key]
    return None

def set_cached_response(query: str, result: dict):
    """设置缓存响应"""
    key = hashlib.md5(query.encode()).hexdigest()
    _response_cache[key] = (result, time.time())

# ============================================
# 财经/政治类查询检测（用于来源优先级）
# ============================================

def is_finance_or_politics_query(query: str) -> bool:
    """判断查询是否与财经或政治相关"""
    keywords = [
        # 财经类
        "财经", "股票", "股市", "经济", "finance", "market", "stock",
        "investment", "trade", "银行", "证券", "基金", "财新",
        "央行", "降准", "降息", "A股", "港股", "美股", "IPO",
        "债券", "期货", "外汇", "人民币", "美元", "黄金", "原油",
        "利率", "汇率", "通胀", "CPI", "PPI", "GDP", "PMI",
        "美联储", "人民银行", "证监会", "银保监会", "金融监管",
        "房地产", "房价", "楼市", "基建", "投资", "消费",
        "财报", "业绩", "盈利", "营收", "净利润", "市值",
        # 政治类
        "政治", "政策", "政府", "两会", "人大", "政协",
        "国务院", "中央", "国家", "改革", "开放", "立法",
        "选举", "投票", "议案", "法规", "法律", "司法"
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in keywords)


# Tavily AI 配置（首选）
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
TAVILY_API_BASE = "https://api.tavily.com/search"

# SerpAPI 配置（备用）
SERP_API_KEY = os.environ.get("SERP_API_KEY", "")
SERP_API_BASE = "https://serpapi.com/search"

# 禁止使用的来源（质量差或不可靠）
BLOCKED_SOURCES = {"baike.baidu.com", "baike.com", "baike.so.com"}

# ============================================
# 分层信源优先级体系（Tier System）
# ============================================

SOURCE_TIERS = {
    # T0: 名词解释/百科类（概念解释最优先）
    "T0": {
        "domains": ["wikipedia.org", "wikimedia.org", "britannica.com", "investopedia.com",
                   "wiktionary.org", "wikiwand.com", "encyclopedia.com"],
        "keywords": ["wikipedia", "wikimedia", "encyclopedia", "britannica", "investopedia",
                    "词典", "百科", "definition", "meaning"],
        "description": "百科词条"
    },
    # T1: 政府/官方机构/企业官网
    "T1": {
        "domains": [".gov", ".gov.cn", "who.int", "un.org", "worldbank.org",
                   "wto.org", "imf.org", "cia.gov", "state.gov", "whitehouse.gov",
                   "nhc.gov.cn", "pbc.gov.cn", "csrc.gov.cn", "miit.gov.cn",
                   "cpc.people.com.cn", "npc.gov.cn"],
        "keywords": ["白宫", "国务院", "央行", "证监会", "工信部", "卫健委",
                    "世界卫生组织", "联合国", "政府", "official", "government"],
        "description": "官方机构"
    },
    # T2: 主流媒体 - 海外
    "T2_OVERSEAS": {
        "domains": ["reuters.com", "bbc.com", "bbc.co.uk", "nytimes.com", "wsj.com",
                   "ft.com", "bloomberg.com", "economist.com", "cnn.com",
                   "theguardian.com", "washingtonpost.com", "apnews.com",
                   "forbes.com", "businessinsider.com", "cnbc.com",
                   "aljazeera.com", "dw.com", "france24.com", "spiegel.de"],
        "keywords": ["reuters", "bbc", "nytimes", "new york times", "financial times",
                    "bloomberg", "economist", "cnn", "guardian", "associated press",
                    "al jazeera", "deutsche welle"],
        "description": "海外主流媒体"
    },
    # T2: 主流媒体 - 国内
    "T2_DOMESTIC": {
        "domains": ["xinhuanet.com", "people.com.cn", "caixin.com", "thepaper.cn",
                   "yicai.com", "jiemian.com", "21jingji.com", "cbn.net.cn",
                   "cctv.com", "chinadaily.com.cn", "scmp.com", "huanqiu.com",
                   "guancha.cn", "banyuetan.org", "caijing.com.cn", "stcn.com"],
        "keywords": ["新华网", "人民网", "财新", "澎湃", "第一财经", "界面",
                    "21财经", "环球时报", "观察者", "半月谈", "财经杂志",
                    "证券时报", "经济日报", "光明日报"],
        "description": "国内主流媒体"
    },
    # T3: 自媒体/社交媒体
    "T3": {
        "domains": ["zhihu.com", "weibo.com", "mp.weixin.qq.com", "zhuanlan.zhihu.com",
                   "36kr.com", "huxiu.com", "sspai.com", "ifanr.com",
                   "jianshu.com", "douban.com", "tieba.baidu.com"],
        "keywords": ["知乎", "微博", "公众号", "简书", "豆瓣", "贴吧",
                    "36氪", "虎嗅", "少数派", "爱范儿"],
        "description": "自媒体"
    }
}

# 领域专业媒体映射
DOMAIN_SPECIALISTS = {
    "tech": ["techcrunch.com", "wired.com", "theverge.com", "arstechnica.com",
             "nature.com", "science.org", "ieee.org", "acm.org",
             "github.com", "stackoverflow.com", "developer.mozilla.org"],
    "finance": ["wsj.com", "ft.com", "bloomberg.com", "caixin.com", "yicai.com",
                "reuters.com", "cnbc.com", "barrons.com", "marketwatch.com",
                "investopedia.com", "seekingalpha.com"],
    "medical": ["who.int", "nejm.org", "thelancet.com", "jamanetwork.com", "cdc.gov",
                "nhs.uk", "mayoclinic.org", "webmd.com", "healthline.com",
                "pubmed.ncbi.nlm.nih.gov", "cochrane.org"],
    "science": ["nature.com", "science.org", "sciencedirect.com", "pnas.org",
               "cell.com", "springer.com", "arxiv.org", "pubmed.ncbi.nlm.nih.gov",
               "nationalgeographic.com", "scientificamerican.com"]
}


def classify_source(url: str, title: str = "") -> tuple:
    """
    对来源进行分类，返回 (tier, domain_type, base_score)
    tier: 数字越小优先级越高 (0-4)
    domain_type: 'encyclopedia', 'official', 'overseas', 'domestic', 'social', 'other'
    base_score: 细分排序分数
    """
    if not url:
        return (4, "other", 0)

    url_lower = url.lower()
    title_lower = title.lower()

    # T0: 百科类（名词解释最优先）
    for domain in SOURCE_TIERS["T0"]["domains"]:
        if domain in url_lower:
            return (0, "encyclopedia", 100)
    for keyword in SOURCE_TIERS["T0"]["keywords"]:
        if keyword in title_lower or keyword in url_lower:
            return (0, "encyclopedia", 90)

    # T1: 政府/官方机构
    for domain in SOURCE_TIERS["T1"]["domains"]:
        if domain in url_lower:
            return (1, "official", 100)
    for keyword in SOURCE_TIERS["T1"]["keywords"]:
        if keyword in title_lower or keyword in url_lower:
            return (1, "official", 90)

    # T2: 主流媒体（区分海内外）
    for domain in SOURCE_TIERS["T2_OVERSEAS"]["domains"]:
        if domain in url_lower:
            return (2, "overseas", 100)
    for keyword in SOURCE_TIERS["T2_OVERSEAS"]["keywords"]:
        if keyword in title_lower or keyword in url_lower:
            return (2, "overseas", 90)

    for domain in SOURCE_TIERS["T2_DOMESTIC"]["domains"]:
        if domain in url_lower:
            return (2, "domestic", 95)
    for keyword in SOURCE_TIERS["T2_DOMESTIC"]["keywords"]:
        if keyword in title_lower or keyword in url_lower:
            return (2, "domestic", 90)

    # T3: 自媒体
    for domain in SOURCE_TIERS["T3"]["domains"]:
        if domain in url_lower:
            return (3, "social", 100)
    for keyword in SOURCE_TIERS["T3"]["keywords"]:
        if keyword in title_lower or keyword in url_lower:
            return (3, "social", 90)

    # T4: 其他
    return (4, "other", 0)


def get_source_priority_score(url: str, title: str, query: str) -> int:
    """
    根据查询内容动态计算来源优先级分数
    分数越低优先级越高
    """
    tier, domain_type, base_score = classify_source(url, title)

    if not query:
        return tier * 1000 + base_score

    query_lower = query.lower()
    url_lower = url.lower() if url else ""

    # 名词解释类查询（是什么、什么意思、定义）优先 T0
    is_definition_query = any(kw in query_lower for kw in
        ["是什么", "什么意思", "定义", "wiki", "encyclopedia", "概念", "介绍",
         "meaning", "definition", "what is", "how to", "怎么", "如何"])

    if is_definition_query:
        if tier == 0:
            base_score -= 50  # 大幅优先
        elif tier <= 1:
            base_score -= 20
        else:
            base_score += 20  # 非百科类降级

    # 海外相关查询优先海外媒体
    overseas_keywords = ["美国", "英国", "欧洲", "日本", "国际", "trump", "biden",
                        "fed", "美国大选", "美股", "海外", "us", "uk", "europe",
                        "america", "britis", "japan", "international", "global"]
    if any(kw in query_lower for kw in overseas_keywords):
        if domain_type == "overseas":
            base_score -= 20
        elif domain_type == "domestic":
            base_score += 10  # 国内媒体在海外话题上降级

    # 国内相关查询优先国内媒体
    domestic_keywords = ["中国", "国内", "北京", "上海", "深圳", "政策", "两会",
                        "央行降准", "chinese", "china", "beijing", "shanghai"]
    if any(kw in query_lower for kw in domestic_keywords):
        if domain_type == "domestic":
            base_score -= 20
        elif domain_type == "overseas":
            base_score += 10
        # 国内政策类查询优先财新
        if "caixin.com" in url_lower:
            base_score -= 15

    # 政治类查询优先财新
    politics_keywords = ["政治", "政策", "政府", "两会", "人大", "国务院", "中央"]
    if any(kw in query_lower for kw in politics_keywords):
        if "caixin.com" in url_lower:
            base_score -= 20  # 政治类查询财新优先

    # 专业领域匹配
    tech_keywords = ["科技", "ai", "人工智能", "tech", "apple", "google", "microsoft",
                    "软件", "硬件", "芯片", "半导体", "technology", "software"]
    if any(kw in query_lower for kw in tech_keywords):
        if any(d in url_lower for d in DOMAIN_SPECIALISTS["tech"]):
            base_score -= 15

    finance_keywords = ["财经", "股票", "股市", "经济", "finance", "market", "stock",
                       "investment", "trade", "银行", "证券", "基金", "财新", "央行", "降准", "降息"]
    if any(kw in query_lower for kw in finance_keywords):
        if any(d in url_lower for d in DOMAIN_SPECIALISTS["finance"]):
            base_score -= 15
        # 财经类查询优先财新
        if "caixin.com" in url_lower:
            base_score -= 25  # 大幅提升财新优先级

    medical_keywords = ["医学", "健康", "疾病", "疫苗", "medical", "health", "disease",
                       "vaccine", "症状", "治疗", "医院", "医生"]
    if any(kw in query_lower for kw in medical_keywords):
        if any(d in url_lower for d in DOMAIN_SPECIALISTS["medical"]):
            base_score -= 15

    science_keywords = ["科学", "研究", "论文", "science", "research", "paper",
                       "nature", "discovery", "实验"]
    if any(kw in query_lower for kw in science_keywords):
        if any(d in url_lower for d in DOMAIN_SPECIALISTS["science"]):
            base_score -= 15

    # 最终分数 = tier * 1000 + score（tier 权重最高）
    return tier * 1000 + base_score


def smart_filter_and_prioritize(results: List[Dict], query: str) -> List[Dict]:
    """智能过滤和排序来源，根据查询内容动态调整优先级"""
    if not results:
        return results

    # 过滤禁止来源
    filtered = [r for r in results if not is_blocked(r.get("url", ""))]

    # 计算每个来源的优先级分数
    scored_results = []
    for r in filtered:
        url = r.get("url", "")
        title = r.get("title", "")
        score = get_source_priority_score(url, title, query)
        scored_results.append((score, r))

    # 按分数排序（分数越低越优先）
    scored_results.sort(key=lambda x: x[0])

    return [r for _, r in scored_results]


# 向后兼容的旧函数（保留但标记为废弃）
def is_authoritative(url: str) -> bool:
    """检查URL是否来自权威媒体（向后兼容）"""
    if not url:
        return False
    tier, _, _ = classify_source(url)
    return tier <= 2  # T0, T1, T2 都算权威


def is_blocked(url: str) -> bool:
    """检查URL是否来自禁止的来源"""
    if not url:
        return False
    url_lower = url.lower()
    return any(blocked in url_lower for blocked in BLOCKED_SOURCES)


def filter_and_prioritize(results: List[Dict]) -> List[Dict]:
    """过滤禁止来源，并将权威来源排在前面（向后兼容，使用 query 为空）"""
    return smart_filter_and_prioritize(results, "")

# Claude API 配置（首选 - antchat.alipay.com）
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
# 使用最快的模型，确保5秒内响应
ANTHROPIC_MODEL = "claude-3-haiku-20240307"  # 最快模型（约1-2秒）
ANTHROPIC_BACKUP_MODEL = "claude-3-haiku-20240307"  # 备用模型

# OpenRouter API 配置（备用 - 使用更快的模型）
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
# 使用 OpenRouter 免费/低成本模型
OPENROUTER_MODEL = "deepseek/deepseek-chat"  # DeepSeek V3，便宜且快
OPENROUTER_BACKUP_MODEL = "qwen/qwen-2.5-7b-instruct"  # 阿里通义千问

# 初始化 Claude 客户端
client = None
if ANTHROPIC_API_KEY:
    client = Anthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)


class ExplainRequest(BaseModel):
    query: str


class Source(BaseModel):
    title: str
    url: str


class ExplainResponse(BaseModel):
    explanation: str
    sources: List[Source]


async def search_with_tavily_async(query: str) -> List[Dict]:
    """异步使用 Tavily AI 搜索（3秒超时）"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TAVILY_API_BASE,
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 3,
                    "include_raw_content": False
                },
                timeout=aiohttp.ClientTimeout(total=3.0)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    for item in data.get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", "")
                        })
                    return results
                else:
                    print(f"Tavily API 错误: {response.status}")
                    return []
    except asyncio.TimeoutError:
        print("[Tavily] 搜索超时，继续用 AI 生成")
        return []
    except Exception as e:
        print(f"Tavily 搜索请求错误: {e}")
        return []


def search_with_tavily(query: str) -> List[Dict]:
    """同步包装（用于兼容旧代码）"""
    try:
        response = requests.post(
            TAVILY_API_BASE,
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 3,
                "include_raw_content": False
            },
            timeout=1.5
        )
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")
                })
            return results
        return []
    except Exception as e:
        print(f"Tavily 搜索错误: {e}")
        return []


def search_with_serpapi(query: str) -> List[Dict]:
    """使用 SerpAPI 搜索"""
    params = {
        "api_key": SERP_API_KEY,
        "q": query,
        "num": 8,
        "engine": "google",
    }

    try:
        response = requests.get(SERP_API_BASE, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            results = []

            # 提取搜索结果
            if "organic_results" in data:
                for item in data["organic_results"][:8]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", "")
                    })

            # 如果没有结果，尝试新闻搜索
            if not results and "news_results" in data:
                for item in data["news_results"][:8]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", "")
                    })

            return results
        else:
            print(f"SerpAPI 错误: {response.status_code}")
            return []
    except Exception as e:
        print(f"搜索请求错误: {e}")
        return []


async def search_with_serpapi_async(query: str) -> List[Dict]:
    """异步使用 SerpAPI 搜索（5秒超时）"""
    params = {
        "api_key": SERP_API_KEY,
        "q": query,
        "num": 8,
        "engine": "google",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                SERP_API_BASE,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5.0)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []

                    # 提取搜索结果
                    if "organic_results" in data:
                        for item in data["organic_results"][:8]:
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", "")
                            })

                    # 如果没有结果，尝试新闻搜索
                    if not results and "news_results" in data:
                        for item in data["news_results"][:8]:
                            results.append({
                                "title": item.get("title", ""),
                                "url": item.get("link", ""),
                                "snippet": item.get("snippet", "")
                            })

                    print(f"[SerpAPI] 搜索成功，获取 {len(results)} 条结果")
                    return results
                else:
                    print(f"[SerpAPI] API 错误: {response.status}")
                    return []
    except asyncio.TimeoutError:
        print("[SerpAPI] 搜索超时")
        return []
    except Exception as e:
        print(f"[SerpAPI] 搜索请求错误: {e}")
        return []


async def search_with_fallback(query: str) -> List[Dict]:
    """
    双保险搜索：Tavily (主) → SerpAPI (备)
    - 首先尝试 Tavily 搜索（3秒超时）
    - 如果 Tavily 失败或返回空结果，自动切换到 SerpAPI（5秒超时）
    """
    # 首先尝试 Tavily
    try:
        print(f"[Search] 尝试 Tavily 搜索: {query}")
        tavily_results = await search_with_tavily_async(query)
        if tavily_results:
            print(f"[Tavily] 搜索成功，获取 {len(tavily_results)} 条结果")
            return tavily_results
        else:
            print("[Tavily] 返回空结果，准备切换到 SerpAPI")
    except Exception as e:
        print(f"[Tavily] 搜索失败: {e}，准备切换到 SerpAPI")

    # Tavily 失败或为空，切换到 SerpAPI
    print(f"[Search] Tavily failed, trying SerpAPI: {query}")
    try:
        serpapi_results = await search_with_serpapi_async(query)
        if serpapi_results:
            print(f"[SerpAPI] 备用搜索成功，获取 {len(serpapi_results)} 条结果")
        else:
            print("[SerpAPI] 备用搜索也返回空结果")
        return serpapi_results
    except Exception as e:
        print(f"[SerpAPI] 备用搜索失败: {e}")
        return []


async def generate_with_openrouter_async(prompt: str, model: str = None) -> str:
    """异步使用 OpenRouter API 生成解释（6秒超时）"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://lazy-bag.local",
        "X-Title": "LazyBag"
    }
    payload = {
        "model": model or OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 120,  # 进一步减少token数
        "temperature": 0.3  # 降低随机性提速
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OPENROUTER_API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=6)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    text = await response.text()
                    print(f"OpenRouter API 错误: {response.status} - {text}")
                    raise Exception("OpenRouter API failed")
    except asyncio.TimeoutError:
        print("[OpenRouter] AI 生成超时")
        raise
    except Exception as e:
        print(f"OpenRouter 请求错误: {e}")
        raise


def generate_with_openrouter(prompt: str, model: str = None) -> str:
    """同步包装（6秒超时）"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json; charset=utf-8",
        "HTTP-Referer": "https://lazy-bag.local",
        "X-Title": "LazyBag"
    }
    payload = {
        "model": model or OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 120,
        "temperature": 0.3
    }
    try:
        response = requests.post(
            f"{OPENROUTER_API_BASE}/chat/completions",
            headers=headers,
            json=payload,
            timeout=6
        )
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"OpenRouter API 错误: {response.status_code} - {response.text}")
            raise Exception("OpenRouter API failed")
    except Exception as e:
        print(f"OpenRouter 请求错误: {e}")
        raise


def clean_ai_output(text: str) -> str:
    """清洗 AI 输出，移除标题、注释等多余内容"""
    if not text:
        return text

    import re

    # 移除 markdown 标题
    text = re.sub(r'^\s*#+\s*.+\n*', '', text, flags=re.MULTILINE)
    # 移除加粗标题格式：**标题**
    text = re.sub(r'^\s*\*\*[^*]+[:：][^*]+\*\*\s*', '', text)
    text = re.sub(r'^\s*\*\*[^*]+\*\*\s*', '', text)
    # 移除结尾括号注释
    text = re.sub(r'\s*（注[：:][^）]*）$', '', text)
    text = re.sub(r'\s*\(注[：:][^)]*\)$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*（[^）]*严格遵循[^）]*）$', '', text)
    text = re.sub(r'\s*\([^)]*strictly[^)]*\)$', '', text, flags=re.IGNORECASE)
    # 移除 "以上..." 结尾固定搭配
    text = re.sub(r'\s*以上(?:内容|信息|总结).*?$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*以上$', '', text)
    # 移除常见废话前缀
    text = re.sub(r'^(?:以下是|总结如下|解释如下|回答[：:])\s*', '', text)
    # 规范化空白
    text = text.strip()

    return text


async def generate_ai_explanation_async(query: str, search_results: List[Dict]) -> str:
    """异步生成 AI 解释（基于搜索结果信源验证）"""
    # 构建搜索上下文（如果有的话）
    if search_results:
        context_parts = []
        for i, item in enumerate(search_results[:3], 1):  # 使用3个来源，更全面
            title = item.get("title", "")
            # 优先使用财新全文，否则使用 snippet
            content = item.get("full_content", "") or item.get("snippet", "")
            # 限制长度，避免超出 token 限制
            if len(content) > 400:
                content = content[:400] + "..."
            if title or content:
                # 标记财新来源
                source_tag = "[财新] " if item.get("source") == "caixin" else ""
                context_parts.append(f"{i}. {source_tag}{title}: {content}")
        context = "\n".join(context_parts)

        # 基于信源的提示词（强调使用搜索结果）
        prompt = f"""基于以下搜索结果，解释「{query}」：

{context}

要求：
1. 必须基于上述信源内容回答，不要依赖常识或训练数据
2. 1-2句话，50-80字
3. 直接回答，无标题
4. 如果信源内容矛盾或不足，请如实说明"""
    else:
        # 无搜索结果时的降级提示词
        prompt = f"""解释「{query}」

（注意：未找到相关搜索结果，请基于常识简要回答）

要求：
1. 1-2句话，50-80字
2. 直接回答，无标题
3. 说明这是基于常识的解释"""

    # 首选：Claude API (antchat - token 容量大)
    if client:
        try:
            print("[AI] 尝试 Claude API...")
            message = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.messages.create(
                        model="claude-3-haiku",
                        max_tokens=120,
                        messages=[{"role": "user", "content": prompt}]
                    )
                ),
                timeout=8
            )
            # 处理响应
            if isinstance(message, str):
                # antchat 可能返回字符串
                if message and len(message) > 15:
                    print(f"[AI] Claude (string) 生成成功，长度: {len(message)}")
                    return clean_ai_output(message)
            elif hasattr(message, 'content') and message.content:
                result = ""
                for block in message.content:
                    if hasattr(block, 'text'):
                        result += block.text
                if result and len(result) > 15:
                    print(f"[AI] Claude 生成成功，长度: {len(result)}")
                    return clean_ai_output(result)
            print("[AI] Claude 返回空响应")
        except asyncio.TimeoutError:
            print("[AI] Claude 超时")
        except Exception as e:
            print(f"[AI] Claude 错误: {e}")

    # 备用：OpenRouter（DeepSeek 模型）
    if OPENROUTER_API_KEY:
        try:
            print("[AI] 尝试 OpenRouter...")
            result = await generate_with_openrouter_async(prompt, model=OPENROUTER_MODEL)
            if result and len(result) > 15:
                print(f"[AI] OpenRouter 生成成功，长度: {len(result)}")
                return clean_ai_output(result)
        except asyncio.TimeoutError:
            print("[AI] OpenRouter 超时")
        except Exception as e:
            print(f"[AI] OpenRouter 错误: {e}")

    # 如果所有 AI 都失败，返回降级提示
    print("[AI] 所有模型失败，返回降级提示")
    return f"{query}是一个常被讨论的话题。AI服务暂时不可用，请稍后重试。"


def generate_ai_explanation(query: str, search_results: List[Dict]) -> str:
    """同步包装（向后兼容）"""
    # 构建搜索上下文
    if search_results:
        context_parts = []
        for i, item in enumerate(search_results[:2], 1):
            title = item.get("title", "")
            # 优先使用财新全文
            content = item.get("full_content", "") or item.get("snippet", "")
            if len(content) > 300:
                content = content[:300] + "..."
            if title or content:
                source_tag = "[财新] " if item.get("source") == "caixin" else ""
                context_parts.append(f"{i}. {source_tag}{title}: {content}")
        context = "\n".join(context_parts)
    else:
        context = "（无搜索结果，请基于常识回答）"

    prompt = f"解释「{query}」：{context}\n\n要求：1-2句话，50-80字，直接回答，无标题"

    # 首选：OpenRouter GPT-4o-mini（6秒超时）
    if OPENROUTER_API_KEY:
        try:
            result = generate_with_openrouter(prompt, model=OPENROUTER_MODEL)
            if result and len(result) > 15:
                print(f"[AI] GPT-4o-mini 生成成功，长度: {len(result)}")
                return clean_ai_output(result)
        except Exception as e:
            print(f"[AI] OpenRouter 错误: {e}")

    # 备用：使用 Claude
    if client:
        try:
            message = client.messages.create(
                model="claude-3-haiku",
                max_tokens=120,
                messages=[{"role": "user", "content": prompt}]
            )
            if message and hasattr(message, 'content') and message.content:
                result = ""
                for block in message.content:
                    if hasattr(block, 'text'):
                        result += block.text
                if result and len(result) > 15:
                    print(f"[AI] Claude 生成成功，长度: {len(result)}")
                    return clean_ai_output(result)
        except Exception as e:
            print(f"[AI] Claude 错误: {e}")

    return f"{query}是一个常被讨论的话题。AI服务暂时不可用，请稍后重试。"


@app.post("/api/explain", response_model=ExplainResponse)
async def explain_keyword(request: ExplainRequest):
    """获取关键词的懒人包解释（带缓存 + 信源验证）

    执行流程：
    1. 检查缓存（24小时TTL）
    2. 搜索获取可靠信源（Tavily -> SerpAPI fallback）
    3. 智能过滤排序来源
    4. 基于搜索结果生成 AI 总结（信源验证）
    """
    query = request.query.strip()

    if not query:
        raise HTTPException(status_code=400, detail="查询不能为空")

    print(f"[API] 收到查询: {query}")

    # 检查缓存（缓存现在包含搜索结果和 AI 总结）
    cached = get_cached_response(query)
    if cached:
        print(f"[Cache] 命中缓存: {query}")
        return ExplainResponse(**cached)

    # 串行执行：先搜索获取可靠信源，再基于信源生成 AI 总结
    start_time = time.time()

    # 1. 先执行搜索获取可靠信源（带 fallback：Tavily -> SerpAPI）
    print(f"[Search] 开始搜索: {query}")
    search_results = await search_with_fallback(query)
    if search_results is None:
        search_results = []
    print(f"[Debug] 搜索返回结果数: {len(search_results)}")

    # 2. 智能过滤和排序来源（传入 query 进行上下文感知）
    print(f"[Debug] 过滤前结果数: {len(search_results)}")
    search_results = smart_filter_and_prioritize(search_results, query)
    print(f"[Debug] 过滤后结果数: {len(search_results)}")

    # 3. 基于搜索结果生成 AI 总结（信源验证）
    print(f"[AI] 基于 {len(search_results)} 条搜索结果生成解释...")
    explanation = await generate_ai_explanation_async(query, search_results)

    elapsed = time.time() - start_time
    print(f"[API] 总耗时: {elapsed:.2f}s")

    # 构建来源列表（格式：机构名：标题）
    sources = []
    skipped_count = 0
    for item in search_results:
        title = item.get("title", "")
        url = item.get("url", "")
        if not title or not url:
            skipped_count += 1
            print(f"[Debug] 跳过无效结果: title={title!r}, url={url!r}")
            continue

        # 提取来源名称
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            # 映射常见域名到中文名称
            domain_clean = domain.replace("www.", "").lower()
            source_map = {
                "wikipedia.org": "Wikipedia",
                "zh.wikipedia.org": "维基百科",
                "en.wikipedia.org": "Wikipedia",
                "zhihu.com": "知乎",
                "reuters.com": "路透社",
                "bbc.com": "BBC",
                "bbc.co.uk": "BBC",
                "cnn.com": "CNN",
                "nytimes.com": "纽约时报",
                "wsj.com": "华尔街日报",
                "ft.com": "金融时报",
                "bloomberg.com": "彭博社",
                "theguardian.com": "卫报",
                "forbes.com": "福布斯",
                "techcrunch.com": "TechCrunch",
                "wired.com": "Wired",
                "nature.com": "Nature",
                "science.org": "Science",
                "xinhua.net": "新华网",
                "people.com.cn": "人民网",
                "sina.com.cn": "新浪",
                "sohu.com": "搜狐",
                "ifeng.com": "凤凰网",
                "tencent.com": "腾讯",
                "caixin.com": "财新",
                "yicai.com": "第一财经",
                "thepaper.com": "澎湃",
            }
            # 处理财新 MCP 来源
            if item.get("source") == "caixin":
                source_name = "财新"
            else:
                source_name = source_map.get(domain_clean, domain.replace("www.", "").split(".")[-2].capitalize())
            display_title = f"{source_name}：{title}"
        except Exception as e:
            print(f"[Debug] 提取来源名称失败: {e}")
            display_title = title
        sources.append(Source(title=display_title, url=url))

    if skipped_count > 0:
        print(f"[Debug] 共跳过 {skipped_count} 个无效结果，最终来源数: {len(sources)}")

    if len(sources) == 0:
        print(f"[Warning] 查询 '{query}' 没有可用来源，搜索返回 {len(search_results)} 条结果但都被过滤或无效")

    response = ExplainResponse(
        explanation=explanation,
        sources=sources
    )

    # 缓存结果（使用 dict() 兼容 Pydantic v1）
    set_cached_response(query, response.dict())

    return response


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "search_engine": "tavily (primary, 3s timeout) -> serpapi (fallback, 5s timeout)",
        "ai_provider": "antchat/claude (primary) -> openrouter (fallback)",
        "model": ANTHROPIC_MODEL,
        "source_priorities": {
            "finance_caixin": "财经类查询优先财新",
            "politics_caixin": "政治类查询优先财新"
        },
        "source_tiers": {
            "T0_encyclopedia": SOURCE_TIERS["T0"]["description"],
            "T1_official": SOURCE_TIERS["T1"]["description"],
            "T2_overseas": SOURCE_TIERS["T2_OVERSEAS"]["description"],
            "T2_domestic": SOURCE_TIERS["T2_DOMESTIC"]["description"],
            "T3_social": SOURCE_TIERS["T3"]["description"]
        },
        "blocked_sources": list(BLOCKED_SOURCES)
    }


if __name__ == "__main__":
    import uvicorn
    # 使用环境变量 PORT（Railway/Render 等云平台使用）
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)