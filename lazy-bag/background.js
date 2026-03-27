// 后台脚本 - 处理右键菜单

// 默认 API 地址（本地开发）
const DEFAULT_API_URL = "http://localhost:8001";

// 获取存储的 API 地址
async function getApiUrl() {
  const result = await chrome.storage.sync.get({ apiUrl: DEFAULT_API_URL });
  return result.apiUrl;
}

// 创建右键菜单
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "lazyBagMenu",
    title: "懒人包",
    contexts: ["selection"]
  });

  chrome.contextMenus.create({
    id: "lazyBagView",
    parentId: "lazyBagMenu",
    title: "查看懒人包",
    contexts: ["selection"]
  });

  // 初始化默认 API 地址
  chrome.storage.sync.get({ apiUrl: null }, (result) => {
    if (!result.apiUrl) {
      chrome.storage.sync.set({ apiUrl: DEFAULT_API_URL });
    }
  });
});

// 处理右键菜单点击
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "lazyBagView" && info.selectionText) {
    // 向 content script 发送消息，显示懒人包
    chrome.tabs.sendMessage(tab.id, {
      action: "showLazyBag",
      text: info.selectionText
    });
  }
});

// 处理来自 content script 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "fetchExplanation") {
    fetchExplanation(message.text)
      .then(result => sendResponse(result))
      .catch(error => sendResponse({ error: error.message }));
    return true; // 异步响应
  }
});

// 调用后端 API 获取解释
async function fetchExplanation(text) {
  const TIMEOUT_MS = 30000; // 30 秒超时

  try {
    const apiUrl = await getApiUrl();
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const response = await fetch(`${apiUrl}/api/explain`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ query: text }),
      signal: controller.signal
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`API 请求失败: ${response.status}`);
    }

    const data = await response.json();

    // 验证响应格式
    if (!data.explanation) {
      throw new Error("API 响应缺少 explanation 字段");
    }

    // 确保 sources 是数组
    if (!data.sources) {
      data.sources = [];
    }

    return data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("请求超时，请稍后重试");
    }
    if (error.message.includes("fetch") || error.message.includes("Failed to fetch")) {
      const apiUrl = await getApiUrl();
      throw new Error(`无法连接到后端服务 (${apiUrl})，请确认服务地址正确且已启动`);
    }
    console.error("获取懒人包失败:", error);
    throw error;
  }
}