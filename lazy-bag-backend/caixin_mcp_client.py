"""
财新 MCP 客户端
通过 SSE 连接财新 MCP 服务获取全文内容
"""

import asyncio
import json
import uuid
from typing import List, Dict, Optional
import aiohttp

CAIXIN_MCP_TOKEN = "BB1Q3wv6seGRZvUA2Cu11g=="
CAIXIN_MCP_SSE_URL = "https://appai.caixin.com/mcpsse/sse"

import os
CAIXIN_MCP_ENABLED = os.environ.get("CAIXIN_MCP_ENABLED", "true").lower() == "true"


class CaixinMCPClient:
    def __init__(self, token: str = None):
        self.token = token or CAIXIN_MCP_TOKEN

    async def search(self, query: str, limit: int = 3) -> List[Dict]:
        if not CAIXIN_MCP_ENABLED:
            return []

        url = f"{CAIXIN_MCP_SSE_URL}?token={self.token}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Accept": "text/event-stream"},
                    timeout=aiohttp.ClientTimeout(total=25.0)
                ) as sse_resp:
                    if sse_resp.status != 200:
                        return []

                    # Read endpoint
                    message_endpoint = None
                    async for line in sse_resp.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith("data: "):
                            data = line[6:]
                            if data.startswith("/mcpsse/messages/"):
                                message_endpoint = f"https://appai.caixin.com{data}"
                                print(f"[Caixin MCP] 会话已建立")
                                break

                    if not message_endpoint:
                        return []

                    # Initialize
                    init_id = str(uuid.uuid4())
                    await session.post(
                        message_endpoint,
                        headers={"Content-Type": "application/json"},
                        json={
                            "jsonrpc": "2.0",
                            "id": init_id,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "lazy-bag", "version": "1.0.0"}
                            }
                        },
                        timeout=aiohttp.ClientTimeout(total=5.0)
                    )

                    # Read initialize response
                    init_ok = False
                    async for line in sse_resp.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                continue
                            try:
                                event = json.loads(data)
                                if event.get("id") == init_id and "result" in event:
                                    init_ok = True
                                    break
                            except:
                                pass

                    if not init_ok:
                        print("[Caixin MCP] 初始化未完成")
                        return []

                    print("[Caixin MCP] 初始化成功")
                    await asyncio.sleep(0.3)

                    # Get tools
                    tools_id = str(uuid.uuid4())
                    await session.post(
                        message_endpoint,
                        headers={"Content-Type": "application/json"},
                        json={"jsonrpc": "2.0", "id": tools_id, "method": "tools/list", "params": {}},
                        timeout=aiohttp.ClientTimeout(total=3.0)
                    )

                    tool_names = []
                    async for line in sse_resp.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                continue
                            try:
                                event = json.loads(data)
                                if event.get("id") == tools_id:
                                    if "result" in event:
                                        tools = event["result"].get("tools", [])
                                        tool_names = [t.get("name") for t in tools]
                                    break
                            except:
                                pass

                    if tool_names:
                        print(f"[Caixin MCP] 可用工具: {tool_names}")

                    # Try different tools (discovered tool name: search_caixin_content)
                    candidates = tool_names if tool_names else ["search_caixin_content", "search", "caixin_search"]
                    articles = []

                    for tool_name in candidates[:3]:  # Try first 3
                        print(f"[Caixin MCP] 尝试: {tool_name}")
                        search_id = str(uuid.uuid4())

                        async with session.post(
                            message_endpoint,
                            headers={"Content-Type": "application/json"},
                            json={
                                "jsonrpc": "2.0",
                                "id": search_id,
                                "method": "tools/call",
                                "params": {"name": tool_name, "arguments": {"keyword": query, "limit": limit}}
                            },
                            timeout=aiohttp.ClientTimeout(total=5.0)
                        ) as resp:
                            if resp.status != 202:
                                continue

                        # Read response
                        found = False
                        async for line in sse_resp.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    continue
                                try:
                                    event = json.loads(data)
                                    if event.get("id") == search_id:
                                        if "result" in event:
                                            content = event["result"].get("content", [])
                                            for item in content:
                                                if item.get("type") == "text":
                                                    try:
                                                        text = json.loads(item.get("text", "{}"))
                                                        if isinstance(text, list):
                                                            articles.extend(text)
                                                        elif isinstance(text, dict):
                                                            if "articles" in text:
                                                                articles.extend(text["articles"])
                                                            elif "title" in text:
                                                                articles.append(text)
                                                    except:
                                                        pass
                                            found = True
                                            break
                                        elif "error" in event:
                                            print(f"[Caixin MCP] 错误: {event['error']}")
                                            break
                                except:
                                    pass

                        if articles:
                            break
                        await asyncio.sleep(0.3)

                    print(f"[Caixin MCP] 找到 {len(articles)} 篇")
                    return self._format_articles(articles)

        except asyncio.TimeoutError:
            print("[Caixin MCP] 超时")
            return []
        except Exception as e:
            print(f"[Caixin MCP] 异常: {e}")
            return []

    def _format_articles(self, articles: List[Dict]) -> List[Dict]:
        results = []
        for a in articles:
            if a:
                results.append({
                    "title": a.get("title", ""),
                    "url": a.get("url", a.get("link", "")),
                    "snippet": a.get("summary", a.get("content", "")[:200]),
                    "source": "caixin",
                    "full_content": a.get("content", ""),
                    "publish_time": a.get("publish_time", a.get("date", "")),
                    "author": a.get("author", "")
                })
        return results


async def search_caixin(query: str, limit: int = 3) -> List[Dict]:
    return await CaixinMCPClient().search(query, limit)


async def test():
    print("=" * 40)
    print("财新 MCP 测试")
    print("=" * 40)
    results = await search_caixin("央行降准", 2)
    print(f"\n结果: {len(results)} 篇")
    for r in results[:2]:
        print(f"  - {r.get('title', 'N/A')[:40]}...")
    return results


if __name__ == "__main__":
    asyncio.run(test())
