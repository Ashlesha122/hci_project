let API = "http://127.0.0.1:5000";
const INTERVAL_MS = 2000;

// Load stored custom server URL if present
if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
  chrome.storage.local.get(["serverUrl"], (res) => {
    if (res && res.serverUrl) {
      API = res.serverUrl.replace(/\/+$/, "");
      const input = document.getElementById("server-url-input");
      if (input) input.value = API;
    }
  });
}

const EMOJI = {
  happy: "😄",
  calm: "🌿",
  focused: "🎯",
  excited: "⚡",
  surprise: "😲",
  tired: "🥱",
  stressed: "😣",
  sad: "😢",
  frustrated: "😤",
};

const LABELS = {
  happy: "Joyful & Smiling",
  calm: "Calm & Centered",
  focused: "Deep Focus",
  excited: "Excited & Energized",
  surprise: "Surprised & Alert",
  tired: "Screen Fatigue",
  stressed: "Tension Detected",
  sad: "Down / Low Energy",
  frustrated: "Frustration Detected",
};

const video = document.getElementById("video");
const wrap = document.querySelector(".video-wrap");
const startBtn = document.getElementById("start-btn");
const stopBtn = document.getElementById("stop-btn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");
const emojiEl = document.getElementById("emoji");
const labelEl = document.getElementById("label");
const subEl = document.getElementById("sub");
const guidanceEl = document.getElementById("guidance");
const livePill = document.getElementById("live-pill");
const canvas = document.getElementById("canvas");

// Background recording elements
const recordingCard = document.getElementById("recording-card");
const savedCounterBadge = document.getElementById("saved-counter-badge");
let totalSavedCheckins = 0;
let tickCount = 0;

// Server settings elements
const serverSettingsBtn = document.getElementById("server-settings-btn");
const serverSettingsBox = document.getElementById("server-settings-box");
const serverUrlInput = document.getElementById("server-url-input");
const saveServerBtn = document.getElementById("save-server-btn");
const serverStatusPill = document.getElementById("server-status-pill");

if (serverUrlInput) serverUrlInput.value = API;

if (serverSettingsBtn && serverSettingsBox) {
  serverSettingsBtn.addEventListener("click", () => {
    serverSettingsBox.style.display = serverSettingsBox.style.display === "none" ? "block" : "none";
  });
}

if (saveServerBtn && serverUrlInput) {
  saveServerBtn.addEventListener("click", () => {
    const newUrl = (serverUrlInput.value || "").trim().replace(/\/+$/, "");
    if (newUrl) {
      API = newUrl;
      if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ serverUrl: API }, () => {
          saveServerBtn.textContent = "Saved!";
          setTimeout(() => { saveServerBtn.textContent = "Save"; }, 1500);
          testServerConnection();
        });
      } else {
        saveServerBtn.textContent = "Saved!";
        setTimeout(() => { saveServerBtn.textContent = "Save"; }, 1500);
      }
    }
  });
}

async function testServerConnection() {
  try {
    const res = await fetch(`${API}/health`, { credentials: "include" });
    const data = await res.json();
    if (data.status === "ok") {
      if (serverStatusPill) {
        serverStatusPill.textContent = "● Connected";
        serverStatusPill.style.color = "#059669";
      }
    }
  } catch (err) {
    if (serverStatusPill) {
      serverStatusPill.textContent = "○ Server Offline";
      serverStatusPill.style.color = "#dc2626";
    }
  }
}

testServerConnection();

const syncUsername = document.getElementById("sync-username");
const openTimelineBtn = document.getElementById("open-timeline-btn");

if (openTimelineBtn) {
  openTimelineBtn.addEventListener("click", () => {
    if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.create) {
      chrome.tabs.create({ url: API });
    } else {
      window.open(API, "_blank");
    }
  });
}

async function syncProfile() {
  try {
    const res = await fetch(`${API}/api/user-profile`, { credentials: "include" });
    const data = await res.json();
    if (data.success) {
      if (syncUsername) syncUsername.textContent = `👤 Synced: ${data.username}`;
      if (data.stats && data.stats.total_checkins && savedCounterBadge) {
        savedCounterBadge.textContent = `${data.stats.total_checkins} total`;
      }
    }
  } catch (err) {
    console.warn("Sync error:", err);
  }
}

syncProfile();

// Breathing widget
const bPacerBtn = document.getElementById("b-pacer-btn");
const bPacerBody = document.getElementById("b-pacer-body");
const bCircle = document.getElementById("b-circle");
const bAction = document.getElementById("b-action");
const bCounter = document.getElementById("b-counter");

let stream = null;
let timer = null;
let busy = false;
let currentMood = "calm";
let bInterval = null;
let bRunning = false;

startBtn.addEventListener("click", start);
stopBtn.addEventListener("click", stop);

function openPermissionTab() {
  if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.create) {
    chrome.tabs.create({ url: chrome.runtime.getURL("permission.html") });
  } else {
    window.open("permission.html", "_blank");
  }
}

async function start() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 480 }, height: { ideal: 360 } },
      audio: false,
    });
    video.srcObject = stream;
    wrap.classList.add("is-on");
    startBtn.hidden = true;
    stopBtn.hidden = false;
    livePill.hidden = false;
    statusEl.textContent = "Live Mood Detection Active";
    statusEl.style.color = "#059669";

    timer = setInterval(tick, INTERVAL_MS);
    setTimeout(tick, 500);
  } catch (err) {
    const isPermError =
      err.name === "NotAllowedError" ||
      err.name === "PermissionDeniedError" ||
      (err.message && (err.message.includes("dismissed") || err.message.includes("denied")));

    if (isPermError) {
      statusEl.innerHTML = `
        <span style="color: #dc2626; font-weight: 600;">Camera permission needed.</span><br />
        <button type="button" id="grant-perm-btn" style="margin-top: 6px; background: #4f46e5; color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 600; cursor: pointer;">
          👉 Click to Allow Camera
        </button>
      `;
      const grantBtn = document.getElementById("grant-perm-btn");
      if (grantBtn) {
        grantBtn.addEventListener("click", () => {
          openPermissionTab();
        });
      }
      openPermissionTab();
    } else {
      statusEl.textContent = "Camera error: " + err.message;
      statusEl.style.color = "#dc2626";
    }
  }
}

function stop() {
  if (timer) clearInterval(timer);
  if (stream) stream.getTracks().forEach((t) => t.stop());
  stream = null;
  video.srcObject = null;
  wrap.classList.remove("is-on");
  startBtn.hidden = false;
  stopBtn.hidden = true;
  livePill.hidden = true;
  statusEl.textContent = "Camera paused";
  statusEl.style.color = "var(--text-muted)";
}

async function tick() {
  if (!video.videoWidth || busy) return;
  busy = true;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0);
  const dataUrl = canvas.toDataURL("image/jpeg", 0.8);

  tickCount++;
  // Auto-record mood periodically every 3 frames (~6 seconds) while user is working
  const shouldSaveMood = (tickCount % 3 === 0);

  try {
    const res = await fetch(`${API}/api/analyze`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: dataUrl, save_mood: shouldSaveMood }),
    });

    if (res.status === 401) {
      statusEl.textContent = "Please sign in at " + API;
      statusEl.style.color = "#d97706";
      return;
    }

    const d = await res.json();
    if (d.success) {
      currentMood = d.dominant_emotion || "calm";
      emojiEl.textContent = EMOJI[currentMood] || "😊";
      labelEl.textContent = LABELS[currentMood] || currentMood;
      subEl.textContent = `${Math.round(d.confidence || 85)}% Match`;
      if (d.hci && d.hci.guidance) guidanceEl.textContent = d.hci.guidance;
      if (d.hci && d.hci.theme) document.body.className = "theme-" + d.hci.theme;

      resultEl.hidden = false;
      if (recordingCard) recordingCard.hidden = false;

      if (shouldSaveMood) {
        totalSavedCheckins++;
        if (savedCounterBadge) {
          savedCounterBadge.textContent = `${totalSavedCheckins} session check-ins`;
        }
        if (totalSavedCheckins % 3 === 0) {
          syncProfile();
        }
      }

      statusEl.textContent = `● Auto-recording mood (${totalSavedCheckins} saved)`;
      statusEl.style.color = "#059669";
    } else {
      statusEl.textContent = d.error || "Looking for face...";
      statusEl.style.color = "var(--text-muted)";
    }
  } catch (err) {
    statusEl.textContent = "Cannot reach server. Check Server URL.";
    statusEl.style.color = "#dc2626";
  } finally {
    busy = false;
  }
}

// 60s Breathing Widget
bPacerBtn.addEventListener("click", () => {
  if (bRunning) {
    bRunning = false;
    bPacerBtn.textContent = "Start";
    bPacerBody.hidden = true;
    if (bInterval) clearInterval(bInterval);
  } else {
    bRunning = true;
    bPacerBtn.textContent = "Stop";
    bPacerBody.hidden = false;
    let phase = 0;
    let sec = 4;
    const phases = [
      { name: "Inhale", class: "inhale" },
      { name: "Hold", class: "hold" },
      { name: "Exhale", class: "exhale" },
    ];
    function setPhase(p) {
      bAction.textContent = phases[p].name;
      bCircle.className = `b-circle ${phases[p].class}`;
    }
    setPhase(0);
    bCounter.textContent = "4s";
    bInterval = setInterval(() => {
      sec--;
      if (sec <= 0) {
        phase = (phase + 1) % phases.length;
        sec = 4;
        setPhase(phase);
      }
      bCounter.textContent = `${sec}s`;
    }, 1000);
  }
});
