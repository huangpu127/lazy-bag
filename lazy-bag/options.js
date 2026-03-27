// 默认 API 地址
const DEFAULT_API_URL = "http://localhost:8001";

// 加载保存的设置
document.addEventListener("DOMContentLoaded", async () => {
  const apiUrlInput = document.getElementById("apiUrl");
  const saveBtn = document.getElementById("saveBtn");
  const resetBtn = document.getElementById("resetBtn");
  const statusDiv = document.getElementById("status");

  // 从 storage 加载设置
  try {
    const result = await chrome.storage.sync.get({ apiUrl: DEFAULT_API_URL });
    apiUrlInput.value = result.apiUrl;
  } catch (error) {
    console.error("加载设置失败:", error);
    apiUrlInput.value = DEFAULT_API_URL;
  }

  // 保存设置
  saveBtn.addEventListener("click", async () => {
    const apiUrl = apiUrlInput.value.trim();

    // 验证 URL 格式
    if (!apiUrl) {
      showStatus("请输入后端服务地址", "error");
      return;
    }

    try {
      // 简单验证 URL 格式
      new URL(apiUrl);
    } catch {
      showStatus("请输入有效的 URL 地址（如 https://api.example.com）", "error");
      return;
    }

    try {
      await chrome.storage.sync.set({ apiUrl: apiUrl });
      showStatus("设置已保存！", "success");

      // 测试连接
      testConnection(apiUrl);
    } catch (error) {
      showStatus(`保存失败: ${error.message}`, "error");
    }
  });

  // 恢复默认
  resetBtn.addEventListener("click", async () => {
    apiUrlInput.value = DEFAULT_API_URL;
    try {
      await chrome.storage.sync.set({ apiUrl: DEFAULT_API_URL });
      showStatus("已恢复默认设置", "success");
    } catch (error) {
      showStatus(`恢复失败: ${error.message}`, "error");
    }
  });

  // 显示状态消息
  function showStatus(message, type) {
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;

    // 3秒后自动隐藏
    setTimeout(() => {
      statusDiv.className = "status";
    }, 3000);
  }

  // 测试后端连接
  async function testConnection(apiUrl) {
    try {
      const response = await fetch(`${apiUrl}/health`, {
        method: "GET",
        headers: { "Content-Type": "application/json" }
      });

      if (response.ok) {
        const data = await response.json();
        showStatus(`连接成功！服务状态: ${data.status}`, "success");
      } else {
        showStatus("连接失败，请检查地址是否正确", "error");
      }
    } catch (error) {
      showStatus(`连接测试失败: ${error.message}`, "error");
    }
  }
});
