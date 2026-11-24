chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "setBadge") {
    const text = message.emoji || "";
    chrome.action.setBadgeText({ text: text ? text.slice(0, 2) : "" });
    chrome.action.setBadgeBackgroundColor({ color: "#3182ce" });
    sendResponse({ ok: true });
    return true;
  }
  return false;
});
