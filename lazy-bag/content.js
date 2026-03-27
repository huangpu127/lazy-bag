// 内容脚本 - 处理选中、悬浮按钮、气泡

let currentSelection = null;
let lazyBagPopup = null;
let hoverButton = null;

// 初始化
document.addEventListener("mouseup", handleMouseUp);
document.addEventListener("mousedown", handleMouseDown);
document.addEventListener("keyup", handleKeyUp);
document.addEventListener("keydown", handleKeyDown);

// 页面滚动时更新气泡位置
window.addEventListener("scroll", handleScroll, { passive: true });

// 监听来自 background 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "showLazyBag") {
    showLazyBag(message.text);
  }
});

function handleMouseUp(event) {
  const selection = window.getSelection();
  const selectedText = selection.toString().trim();

  // 延迟执行，等待选中文本稳定
  setTimeout(() => {
    const newSelection = window.getSelection().toString().trim();
    const newRange = selection.rangeCount > 0 ? selection.getRangeAt(0) : null;

    if (newSelection && newSelection.length > 0 && newRange) {
      const rect = newRange.getBoundingClientRect();
      console.log("[懒人包] 选中文本:", newSelection.substring(0, 50), "位置:", rect);

      // 检查位置是否有效
      if (rect.left === 0 && rect.top === 0 && rect.width === 0 && rect.height === 0) {
        console.warn("[懒人包] 警告：获取到的选区位置为全0，可能选区已丢失");
      }

      // 保存位置信息
      currentSelection = {
        text: newSelection,
        range: {
          left: rect.left,
          top: rect.top,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height
        }
      };
      showHoverButton(currentSelection.range);
    } else {
      hideHoverButton();
    }
  }, 10);
}

function handleMouseDown(event) {
  // 如果点击在气泡或悬浮按钮上，不隐藏
  if (lazyBagPopup && lazyBagPopup.contains(event.target)) {
    return;
  }
  if (hoverButton && hoverButton.contains(event.target)) {
    return;
  }

  // 点击其他地方，关闭懒人包
  hideLazyBag();
}

function handleKeyUp(event) {
  const selection = window.getSelection();
  const selectedText = selection.toString().trim();

  if (selectedText && selectedText.length > 0 && selection.rangeCount > 0) {
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    currentSelection = {
      text: selectedText,
      range: {
        left: rect.left,
        top: rect.top,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height
      }
    };
    showHoverButton(currentSelection.range);
  }
}

// ESC 键关闭懒人包
function handleKeyDown(event) {
  if (event.key === "Escape") {
    hideLazyBag();
  }
}

// 滚动时隐藏悬浮按钮和气泡（因为选区位置已改变）
let scrollTimeout = null;
function handleScroll() {
  if (scrollTimeout) {
    clearTimeout(scrollTimeout);
  }
  scrollTimeout = setTimeout(() => {
    // 滚动后选区位置可能已变化，关闭气泡避免位置错位
    if (lazyBagPopup || hoverButton) {
      hideLazyBag();
    }
  }, 50);
}

// 显示悬浮按钮
function showHoverButton(rect) {
  hideHoverButton();

  hoverButton = document.createElement("div");
  hoverButton.className = "lazy-bag-hover-btn";
  hoverButton.innerHTML = "📦";
  hoverButton.title = "点击查看懒人包";

  // 定位到选中区域上方居中位置（使用 fixed 定位）
  hoverButton.style.position = "fixed";

  // 计算水平位置：以选区中心为基准，按钮居中显示
  const buttonWidth = 32; // 按钮宽度
  let left = rect.left + (rect.width / 2) - (buttonWidth / 2);
  // 边界检查
  left = Math.max(5, Math.min(left, window.innerWidth - buttonWidth - 5));

  // 垂直位置：紧贴选区上方
  let top = rect.top - 32; // 32px 按钮高度 + 间距

  // 如果上方空间不足，显示在选区下方
  if (top < 0) {
    top = rect.bottom + 5;
  }

  hoverButton.style.left = `${left}px`;
  hoverButton.style.top = `${top}px`;
  hoverButton.style.zIndex = "2147483647";

  console.log("[懒人包] 悬浮按钮位置:", left, top, "选区:", rect);

  hoverButton.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (currentSelection) {
      showLazyBag(currentSelection.text);
    }
  });

  document.body.appendChild(hoverButton);
}

function hideHoverButton() {
  if (hoverButton) {
    hoverButton.remove();
    hoverButton = null;
  }
}

// 显示懒人包气泡
async function showLazyBag(text) {
  // 关闭已有的懒人包
  hideLazyBag();

  // 获取选区位置：优先使用已保存的位置，否则重新获取
  let positionRect = null;

  // 1. 首先尝试使用已保存的位置（最可靠）
  if (currentSelection && currentSelection.range) {
    const saved = currentSelection.range;
    // 验证保存的位置是否有效（不是全0）
    if (saved.left !== 0 || saved.top !== 0 || saved.width !== 0 || saved.height !== 0) {
      positionRect = { ...saved };
      console.log("[懒人包] 使用保存的位置:", positionRect);
    }
  }

  // 2. 如果保存的位置无效，尝试重新获取选区
  if (!positionRect) {
    const selection = window.getSelection();
    if (selection.rangeCount > 0) {
      const rect = selection.getRangeAt(0).getBoundingClientRect();
      // 验证新获取的位置是否有效
      if (rect.left !== 0 || rect.top !== 0 || rect.width !== 0 || rect.height !== 0) {
        positionRect = {
          left: rect.left,
          top: rect.top,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height
        };
        console.log("[懒人包] 使用重新获取的位置:", positionRect);
      }
    }
  }

  // 3. 如果仍然无法获取有效位置，使用最后已知位置或默认值
  if (!positionRect) {
    console.warn("[懒人包] 无法获取有效位置，使用默认值");
    // 使用视窗中心作为 fallback
    positionRect = {
      left: window.innerWidth / 2 - 150,
      top: window.innerHeight / 2,
      bottom: window.innerHeight / 2 + 20,
      width: 300,
      height: 20
    };
  }

  // 更新当前选择（包含有效位置）
  currentSelection = {
    text: text,
    range: positionRect
  };

  // 创建气泡
  lazyBagPopup = document.createElement("div");
  lazyBagPopup.className = "lazy-bag-popup";

  // 加载状态
  lazyBagPopup.innerHTML = `
    <div class="lazy-bag-header">
      <span class="lazy-bag-title">懒人包</span>
      <button class="lazy-bag-close">&times;</button>
    </div>
    <div class="lazy-bag-content">
      <div class="lazy-bag-loading">加载中...</div>
    </div>
  `;

  // 定位气泡在选区正上方（使用 fixed 定位，基于保存的位置）
  lazyBagPopup.style.position = "fixed";
  lazyBagPopup.style.zIndex = "2147483647";

  // 先添加到 DOM 以获取实际高度
  document.body.appendChild(lazyBagPopup);

  // 获取气泡实际高度后调整位置
  requestAnimationFrame(() => {
    if (!lazyBagPopup) return;
    const popupRect = lazyBagPopup.getBoundingClientRect();
    const popupHeight = popupRect.height || 150; // 默认估算高度

    // 计算水平位置：以选区中心为基准，气泡居中显示
    let left = positionRect.left + (positionRect.width / 2) - (popupRect.width / 2);
    // 边界检查：不超出视窗左右边界
    left = Math.max(10, Math.min(left, window.innerWidth - popupRect.width - 10));

    // 默认显示在选区正上方
    let top = positionRect.top - popupHeight - 8; // 8px 间距

    // 如果上方空间不足（会超出视窗顶部），则显示在选区下方
    if (top < 0) {
      top = positionRect.bottom + 8;
    }

    lazyBagPopup.style.left = `${left}px`;
    lazyBagPopup.style.top = `${top}px`;

    console.log("[懒人包] 气泡最终位置:", left, top, "选区位置:", positionRect);
  });

  // 绑定关闭事件
  lazyBagPopup.querySelector(".lazy-bag-close").addEventListener("click", (e) => {
    e.stopPropagation();
    hideLazyBag();
  });

  // 调用 API 获取解释
  try {
    const result = await fetchExplanation(text);
    displayExplanation(result);
  } catch (error) {
    displayError(error.message);
  }
}

// 调用 background 脚本获取解释
function fetchExplanation(text) {
  // 限制文本长度，避免请求过大
  const MAX_TEXT_LENGTH = 500;
  const trimmedText = text.length > MAX_TEXT_LENGTH
    ? text.slice(0, MAX_TEXT_LENGTH) + "..."
    : text;

  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({
      action: "fetchExplanation",
      text: trimmedText
    }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error("扩展通信失败，请刷新页面重试"));
        return;
      }
      if (response && response.error) {
        reject(new Error(response.error));
      } else if (response) {
        resolve(response);
      } else {
        reject(new Error("未收到响应"));
      }
    });
  });
}

// 显示解释内容
function displayExplanation(data) {
  if (!lazyBagPopup) return;

  const content = lazyBagPopup.querySelector(".lazy-bag-content");
  const cleanedText = cleanExplanation(data.explanation);

  // 清洗后内容为空，显示错误
  if (!cleanedText) {
    displayError("返回内容为空");
    return;
  }

  // 检查是否有来源
  const hasSources = data.sources && Array.isArray(data.sources) && data.sources.length > 0;

  content.innerHTML = `
    <div class="lazy-bag-text">${escapeHtml(cleanedText)}</div>
    ${hasSources ? `
      <div class="lazy-bag-actions">
        <button class="lazy-bag-sources-btn">查看来源</button>
      </div>
      <div class="lazy-bag-sources" style="display: none;">
        ${data.sources.map(source => `
          <a href="${escapeHtml(source.url || '')}" target="_blank" class="lazy-bag-source-link">
            ${escapeHtml(source.title || '未命名来源')}
          </a>
        `).join("")}
      </div>
    ` : ''}
  `;

  // 只有在有来源时才绑定查看来源按钮事件
  if (hasSources) {
    content.querySelector(".lazy-bag-sources-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      const sourcesDiv = content.querySelector(".lazy-bag-sources");
      const btn = content.querySelector(".lazy-bag-sources-btn");

      if (sourcesDiv.style.display === "none") {
        sourcesDiv.style.display = "block";
        btn.textContent = "收起来源";

        // 展开后重新定位，确保底部在视窗内
        requestAnimationFrame(() => {
          adjustPopupForViewport();
        });
      } else {
        sourcesDiv.style.display = "none";
        btn.textContent = "查看来源";
      }
    });
  }
}

// 调整气泡位置确保在视窗内可见
function adjustPopupForViewport() {
  if (!lazyBagPopup) return;

  const popupRect = lazyBagPopup.getBoundingClientRect();
  const viewportHeight = window.innerHeight;

  // 检查气泡底部是否超出视窗
  if (popupRect.bottom > viewportHeight) {
    const overflow = popupRect.bottom - viewportHeight;
    const currentTop = parseFloat(lazyBagPopup.style.top) || popupRect.top;

    // 向上移动，确保底部可见（留出 10px 边距）
    let newTop = currentTop - overflow - 10;

    // 边界检查：顶部不能超出视窗顶部（至少保留 10px）
    newTop = Math.max(10, newTop);

    lazyBagPopup.style.top = `${newTop}px`;
    console.log("[懒人包] 气泡上移:", newTop, "溢出:", overflow);
  }
}

// 显示错误
function displayError(message) {
  if (!lazyBagPopup) return;

  const content = lazyBagPopup.querySelector(".lazy-bag-content");
  content.innerHTML = `
    <div class="lazy-bag-error">获取失败: ${escapeHtml(message)}</div>
    <div class="lazy-bag-actions">
      <button class="lazy-bag-retry-btn">重试</button>
    </div>
  `;

  // 绑定重试按钮
  content.querySelector(".lazy-bag-retry-btn").addEventListener("click", async (e) => {
    e.stopPropagation();
    if (currentSelection) {
      content.innerHTML = `<div class="lazy-bag-loading">加载中...</div>`;
      try {
        const result = await fetchExplanation(currentSelection.text);
        displayExplanation(result);
      } catch (error) {
        displayError(error.message);
      }
    }
  });
}

// 关闭懒人包
function hideLazyBag() {
  if (lazyBagPopup) {
    lazyBagPopup.remove();
    lazyBagPopup = null;
  }
  hideHoverButton();
}

// 清洗解释内容 - 移除标题、注释等多余格式
function cleanExplanation(text) {
  if (!text) return "";

  return text
    // 移除标题格式：**标题** 或 **新闻稿：标题**
    .replace(/^\*\*[^*]+[:：][^*]+\*\*\s*/m, "")
    .replace(/^\*\*[^*]+\*\*\s*/m, "")
    // 移除结尾括号注释：（注：...）或（注意：...）等
    .replace(/\s*（注[：:][^）]*）$/g, "")
    .replace(/\s*\(注[：:][^)]*\)$/g, "")
    .replace(/\s*（[^）]*严格遵循[^）]*）$/g, "")
    .replace(/\s*\([^)]*strictly[^)]*\)$/gi, "")
    // 移除字数提示括号：（约50字）、（100字左右）、（字数：30）等
    .replace(/\s*（约?\d+[~～至到]?\d*字[左右]?）/g, "")
    .replace(/\s*（字数[：:]\d+[~～至到]?\d*字?）/g, "")
    .replace(/\s*\(约?\d+[~～至到]?\d*字[左右]?\)/g, "")
    .replace(/\s*\(字数[：:]\d+[~～至到]?\d*字?\)/g, "")
    // 移除常见 AI 填充词
    .replace(/\s*以下是[^。]*。/g, "")
    .replace(/^以下是[：:]/g, "")
    .replace(/^回答[：:]/g, "")
    // 移除 markdown 标题
    .replace(/^#+\s*.+\n*/m, "")
    // 规范化空白字符
    .trim();
}

// HTML 转义
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}