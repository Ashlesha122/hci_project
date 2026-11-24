/**
 * MoodPulse • Live Face Mood Reader & Adaptive Workspace
 * Real-Time Vision ML, Dynamic Adaptation, Human Feedback & Persistent History
 */

(function () {
  "use strict";

  // Elements
  const video = document.getElementById("webcam");
  const canvas = document.getElementById("hidden-capture-canvas");
  const overlayCanvas = document.getElementById("overlay-canvas");
  const placeholder = document.getElementById("placeholder");
  const videoContainer = document.querySelector(".video-container");
  const toggleCameraBtn = document.getElementById("toggle-camera-btn");
  const recordMoodBtn = document.getElementById("record-mood-btn");
  const cameraStatusBadge = document.getElementById("camera-status-badge");

  const currentEmoji = document.getElementById("current-emoji");
  const currentLabel = document.getElementById("current-label");
  const currentGuidance = document.getElementById("current-guidance");
  const confidenceBadge = document.getElementById("confidence-badge");
  const hciModeText = document.getElementById("hci-mode-text");
  const brandAvatar = document.getElementById("brand-avatar");
  const adaptiveToggle = document.getElementById("adaptive-toggle");

  const confirmYesBtn = document.getElementById("confirm-yes-btn");
  const distributionBars = document.getElementById("distribution-bars");
  const historyTimeline = document.getElementById("history-timeline");
  const alignmentStat = document.getElementById("alignment-stat");
  const ergonomicText = document.getElementById("ergonomic-text");
  const clearHistoryBtn = document.getElementById("clear-history-btn");
  const saveAlert = document.getElementById("save-alert");

  // Breathing pacer elements
  const togglePacerBtn = document.getElementById("toggle-pacer-btn");
  const pacerCircle = document.getElementById("pacer-circle");
  const pacerAction = document.getElementById("pacer-action");
  const pacerCounter = document.getElementById("pacer-counter");
  const stepInhale = document.getElementById("step-inhale");
  const stepHold = document.getElementById("step-hold");
  const stepExhale = document.getElementById("step-exhale");

  // Extension Modal
  const extModal = document.getElementById("ext-modal");
  const openExtBtn = document.getElementById("open-ext-btn");
  const closeExtBtn = document.getElementById("close-ext-btn");
  const modalGotItBtn = document.getElementById("modal-got-it-btn");
  const testConnBtn = document.getElementById("test-connection-btn");
  const connStatusText = document.getElementById("connection-status-text");

  // State
  let stream = null;
  let intervalTimer = null;
  let isAnalyzing = false;
  let activeEmotion = "calm";
  let activeConfidence = 85.0;
  let pacerInterval = null;
  let pacerRunning = false;
  let frameCount = 0;

  const EMOJI_MAP = {
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

  const LABEL_MAP = {
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

  const THEME_MAP = {
    happy: "joy",
    calm: "calm",
    focused: "focus",
    excited: "excited",
    surprise: "wonder",
    tired: "tired",
    stressed: "stressed",
    sad: "sad",
    frustrated: "frustrated",
  };

  const MOOD_COLOR_MAP = {
    happy: "#ea580c",
    calm: "#4f46e5",
    focused: "#059669",
    excited: "#e11d48",
    surprise: "#7c3aed",
    tired: "#0284c7",
    stressed: "#d97706",
    sad: "#2563eb",
    frustrated: "#b91c1c",
  };

  // Rotating Desk Tips
  const DESK_TIPS = [
    "<strong>Desk Tip:</strong> Unclench your jaw and gently drop your shoulders away from your ears.",
    "<strong>Desk Tip:</strong> Follow the 20-20-20 rule: every 20 minutes, gaze at an object 20 feet away for 20 seconds.",
    "<strong>Desk Tip:</strong> Keep your screen at eye level to prevent neck stiffness during long work sessions.",
    "<strong>Desk Tip:</strong> Take a slow, deep belly breath to instantly reset your nervous system.",
    "<strong>Desk Tip:</strong> A quick 2-minute standing stretch boosts mental clarity and blood flow.",
    "<strong>Desk Tip:</strong> Rest your palms over your eyes for 15 seconds to ease screen glare fatigue.",
    "<strong>Desk Tip:</strong> Keep both feet flat on the floor and support your lower back.",
    "<strong>Desk Tip:</strong> Drink a glass of water—mild dehydration is often mistaken for mental fatigue.",
    "<strong>Desk Tip:</strong> Roll your wrists and stretch your fingers to relieve typing strain.",
    "<strong>Desk Tip:</strong> Step away from the monitor during breaks to give your eyes a true reset.",
  ];
  let tipIdx = Math.floor(Math.random() * DESK_TIPS.length);
  if (ergonomicText) ergonomicText.innerHTML = DESK_TIPS[tipIdx];

  setInterval(() => {
    tipIdx = (tipIdx + 1) % DESK_TIPS.length;
    if (ergonomicText) ergonomicText.innerHTML = DESK_TIPS[tipIdx];
  }, 25000);

  // --- CAMERA MANAGEMENT ---
  if (toggleCameraBtn) {
    toggleCameraBtn.addEventListener("click", () => {
      if (stream) {
        stopCamera();
      } else {
        startCamera();
      }
    });
  }

  async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("Camera access requires opening this app at http://localhost:5000 in your browser.\n\n(Browsers restrict camera access when opened via network IP without HTTPS.)");
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      });
      video.srcObject = stream;
      videoContainer.classList.add("live");
      toggleCameraBtn.textContent = "⏸ Pause Check-in";
      toggleCameraBtn.classList.remove("btn-primary");
      toggleCameraBtn.classList.add("btn-secondary");
      cameraStatusBadge.textContent = "Live Tracking Active";
      cameraStatusBadge.classList.add("active");

      if (recordMoodBtn) {
        recordMoodBtn.disabled = false;
      }

      // Initial capture then check every 2 seconds
      setTimeout(() => captureAndAnalyze(), 500);
      intervalTimer = setInterval(() => {
        if (!isAnalyzing && stream) {
          captureAndAnalyze();
        }
      }, 2000);
    } catch (err) {
      alert("Camera access denied or unavailable: " + err.message);
    }
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
    if (intervalTimer) {
      clearInterval(intervalTimer);
      intervalTimer = null;
    }
    video.srcObject = null;
    videoContainer.classList.remove("live");
    toggleCameraBtn.textContent = "▶ Start Check-in";
    toggleCameraBtn.classList.add("btn-primary");
    toggleCameraBtn.classList.remove("btn-secondary");
    cameraStatusBadge.textContent = "Camera Inactive";
    cameraStatusBadge.classList.remove("active");
    clearOverlay();
  }

  // --- CAPTURE & INFERENCE ---
  async function captureAndAnalyze() {
    if (!video.videoWidth || isAnalyzing) return;
    isAnalyzing = true;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.85);

    frameCount++;
    // Auto-save every 5 frames (~10 seconds)
    const shouldSave = frameCount % 5 === 0;

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: dataUrl, save_mood: shouldSave }),
      });

      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }

      const data = await res.json();
      if (data.success) {
        updateInterface(data);
        if (data.history && data.history.length > 0) {
          renderHistory(data.history);
        }
        if (data.stats) {
          updateStatsDisplay(data.stats);
        }
      } else {
        handleNoFace(data.error || "Looking for face...");
      }
    } catch (err) {
      console.warn("Analysis paused:", err);
    } finally {
      isAnalyzing = false;
    }
  }

  function handleNoFace(msg) {
    overlayCanvas.width = overlayCanvas.clientWidth;
    overlayCanvas.height = overlayCanvas.clientHeight;
    const ctx = overlayCanvas.getContext("2d");
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
    ctx.fillRect(20, 20, overlayCanvas.width - 40, 36);
    ctx.fillStyle = "#ffffff";
    ctx.font = "bold 13px -apple-system, BlinkMacSystemFont, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(msg, overlayCanvas.width / 2, 43);
  }

  // --- REAL-TIME UI UPDATES ---
  function updateInterface(data) {
    const emotion = data.dominant_emotion || "calm";
    activeEmotion = emotion;
    activeConfidence = data.confidence || 75.0;
    const hci = data.hci || {};

    // 1. Dominant Emotion & Real Confidence Badge
    if (currentEmoji) currentEmoji.textContent = EMOJI_MAP[emotion] || "😊";
    if (currentLabel) currentLabel.textContent = LABEL_MAP[emotion] || emotion;
    if (confidenceBadge) {
      confidenceBadge.hidden = false;
      confidenceBadge.textContent = `${Math.round(activeConfidence)}% Match`;
    }
    if (currentGuidance && hci.guidance) currentGuidance.textContent = hci.guidance;
    if (hciModeText && hci.badge) hciModeText.textContent = hci.badge;

    // 2. Dynamic Adaptive Theme
    if (adaptiveToggle && adaptiveToggle.checked && hci.theme) {
      document.body.className = `theme-${hci.theme}`;
      if (brandAvatar) brandAvatar.textContent = EMOJI_MAP[emotion] || "😊";
    }

    // 3. Draw accurate bounding box on detected face
    if (data.region) {
      drawFaceBox(data.region);
    }

    // 4. Render real confidence distribution bars
    if (data.emotions) {
      renderDistributionBars(data.emotions);
    }

    // 5. Breathing highlight if tension detected
    const breathingCard = document.getElementById("breathing-card");
    if (breathingCard) {
      breathingCard.style.borderColor = (hci.pacer_suggested && !pacerRunning) ? "var(--primary)" : "var(--border)";
    }

    // 6. Update alignment stats
    updateStatsDisplay(data.stats);
  }

  function drawFaceBox(box) {
    overlayCanvas.width = overlayCanvas.clientWidth;
    overlayCanvas.height = overlayCanvas.clientHeight;
    const ctx = overlayCanvas.getContext("2d");
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    if (!box.w || !box.h || !video.videoWidth) return;
    const scaleX = overlayCanvas.width / video.videoWidth;
    const scaleY = overlayCanvas.height / video.videoHeight;

    const rx = (video.videoWidth - box.x - box.w) * scaleX;
    const ry = box.y * scaleY;
    const rw = box.w * scaleX;
    const rh = box.h * scaleY;

    const boxColor = MOOD_COLOR_MAP[activeEmotion] || "rgba(79, 70, 229, 0.9)";
    ctx.strokeStyle = boxColor;
    ctx.lineWidth = 3.5;
    ctx.strokeRoundRect(rx, ry, rw, rh, 12);
  }

  function clearOverlay() {
    const ctx = overlayCanvas.getContext("2d");
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  }

  function renderDistributionBars(emotions) {
    if (!distributionBars) return;
    distributionBars.innerHTML = "";
    const sorted = Object.entries(emotions).sort((a, b) => b[1] - a[1]);
    sorted.slice(0, 5).forEach(([label, pct]) => {
      const barColor = MOOD_COLOR_MAP[label] || "var(--primary)";
      const row = document.createElement("div");
      row.className = "dist-row";
      row.innerHTML = `
        <span class="dist-label">${label}</span>
        <div class="dist-track"><div class="dist-fill" style="width: ${pct}%; background: ${barColor};"></div></div>
        <span class="dist-val">${Math.round(pct)}%</span>
      `;
      distributionBars.appendChild(row);
    });
  }

  // --- NOTIFICATION TOAST ---
  function showToast(message) {
    if (!saveAlert) return;
    saveAlert.textContent = message;
    saveAlert.style.display = "block";
    saveAlert.classList.add("visible");
    setTimeout(() => {
      saveAlert.classList.remove("visible");
      setTimeout(() => { saveAlert.style.display = "none"; }, 300);
    }, 3000);
  }

  // --- PERSISTENT HISTORY RENDERING ---
  function renderHistory(items) {
    if (!historyTimeline) return;
    historyTimeline.innerHTML = "";

    if (!items || items.length === 0) {
      historyTimeline.innerHTML = `
        <div class="timeline-empty">
          No check-ins saved yet. Turn on camera and tap "Record This Mood" or confirm your mood above!
        </div>
      `;
      return;
    }

    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "timeline-item";

      const mood = item.emotion || "calm";
      const emoji = EMOJI_MAP[mood] || "🌿";
      const label = LABEL_MAP[mood] || mood;
      const conf = Math.round(item.confidence || 85);

      // Format timestamp nicely
      let formattedTime = item.created_at || "";
      if (formattedTime.includes(" ")) {
        const timePart = formattedTime.split(" ")[1];
        formattedTime = timePart;
      }

      let tagHtml = "";
      if (item.confirmed === 1) {
        tagHtml = '<span class="hist-tag tag-confirmed">✓ Confirmed</span>';
      } else if (item.corrected_to) {
        tagHtml = '<span class="hist-tag tag-adjusted">✏️ Adjusted</span>';
      } else {
        tagHtml = '<span class="hist-tag tag-checkin">Checked In</span>';
      }

      row.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-size: 18px;">${emoji}</span>
          <div>
            <strong>${label}</strong>
            <span style="color: var(--text-muted); font-size: 11px;">(${conf}%)</span>
            ${tagHtml}
          </div>
        </div>
        <span style="color: var(--text-muted); font-size: 11px; font-weight: 500;">${formattedTime}</span>
      `;
      historyTimeline.appendChild(row);
    });
  }

  function updateStatsDisplay(stats) {
    if (!alignmentStat) return;
    if (stats && stats.total_checkins > 0) {
      const calCount = stats.learning_count || 0;
      const calText = calCount > 0 ? ` • ${calCount} Learned Adaptations 🎯` : "";
      alignmentStat.textContent = `${stats.total_checkins} Total Check-ins (${stats.confirmed_count} Confirmed)${calText}`;
    } else {
      alignmentStat.textContent = "No check-ins recorded yet";
    }
  }

  // --- MANUAL RECORD BUTTON ---
  if (recordMoodBtn) {
    recordMoodBtn.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/save-checkin", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            emotion: activeEmotion,
            confidence: activeConfidence,
          }),
        });
        const data = await res.json();
        if (data.success) {
          showToast(`✓ Recorded: ${LABEL_MAP[activeEmotion] || activeEmotion} (${Math.round(activeConfidence)}%)`);
          renderHistory(data.history);
          updateStatsDisplay(data.stats);
        }
      } catch (err) {
        console.error("Save error:", err);
      }
    });
  }

  // --- CLEAR HISTORY BUTTON ---
  if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener("click", async () => {
      if (!confirm("Are you sure you want to clear your saved mood history?")) return;
      try {
        const res = await fetch("/api/clear-history", { method: "POST" });
        const data = await res.json();
        if (data.success) {
          renderHistory([]);
          updateStatsDisplay(data.stats);
          showToast("Timeline cleared.");
        }
      } catch (err) {
        console.error("Clear error:", err);
      }
    });
  }

  // --- HUMAN FEEDBACK & ACCURACY RECORDING ---
  if (confirmYesBtn) {
    confirmYesBtn.addEventListener("click", async () => {
      const confirmedMood = activeEmotion;
      try {
        const res = await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_correct: true, predicted_mood: confirmedMood }),
        });
        const data = await res.json();
        showToast(`✓ Confirmed & saved: ${LABEL_MAP[confirmedMood] || confirmedMood}`);
        if (data.history) renderHistory(data.history);
        updateStatsDisplay(data.stats);
      } catch {}
    });
  }

  document.querySelectorAll(".chip-btn").forEach((chip) => {
    chip.addEventListener("click", async () => {
      const prevMood = activeEmotion;
      const corrected = chip.getAttribute("data-mood");
      activeEmotion = corrected;
      currentEmoji.textContent = EMOJI_MAP[corrected] || "😊";
      currentLabel.textContent = LABEL_MAP[corrected] || corrected;

      if (adaptiveToggle && adaptiveToggle.checked) {
        document.body.className = `theme-${THEME_MAP[corrected] || "calm"}`;
        if (brandAvatar) brandAvatar.textContent = EMOJI_MAP[corrected] || "😊";
      }

      try {
        const res = await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            is_correct: false,
            predicted_mood: prevMood,
            corrected_mood: corrected,
          }),
        });
        const data = await res.json();
        showToast(`✓ Adjusted & recorded: ${LABEL_MAP[corrected] || corrected}`);
        if (data.history) renderHistory(data.history);
        updateStatsDisplay(data.stats);
      } catch {}
    });
  });

  // --- GUIDED PACED BREATHING (4-4-4) ---
  if (togglePacerBtn) {
    togglePacerBtn.addEventListener("click", () => {
      const pacerWrap = document.getElementById("pacer-container");
      if (pacerRunning) {
        stopPacer();
        if (pacerWrap) pacerWrap.style.display = "none";
      } else {
        startPacer();
        if (pacerWrap) pacerWrap.style.display = "block";
      }
    });
  }

  function startPacer() {
    pacerRunning = true;
    togglePacerBtn.textContent = "Stop Breather";
    let phase = 0;
    let secondsLeft = 4;

    const phases = [
      { name: "Inhale", class: "inhale", chip: stepInhale },
      { name: "Hold", class: "hold", chip: stepHold },
      { name: "Exhale", class: "exhale", chip: stepExhale },
    ];

    function applyPhase(idx) {
      phases.forEach((p, i) => {
        if (p.chip) p.chip.classList.toggle("active", i === idx);
      });
      pacerAction.textContent = phases[idx].name;
      pacerCircle.className = `pacer-circle ${phases[idx].class}`;
    }

    applyPhase(0);
    pacerCounter.textContent = "4s";

    pacerInterval = setInterval(() => {
      secondsLeft--;
      if (secondsLeft <= 0) {
        phase = (phase + 1) % phases.length;
        secondsLeft = 4;
        applyPhase(phase);
      }
      pacerCounter.textContent = `${secondsLeft}s`;
    }, 1000);
  }

  function stopPacer() {
    pacerRunning = false;
    togglePacerBtn.textContent = "Start 60s Breather";
    if (pacerInterval) clearInterval(pacerInterval);
    pacerCircle.className = "pacer-circle";
    pacerAction.textContent = "Rest";
    pacerCounter.textContent = "";
    [stepInhale, stepHold, stepExhale].forEach((c) => {
      if (c) c.classList.remove("active");
    });
  }

  // --- BROWSER EXTENSION MODAL ---
  if (openExtBtn && extModal) {
    openExtBtn.addEventListener("click", () => { extModal.hidden = false; });
  }
  if (closeExtBtn && extModal) {
    closeExtBtn.addEventListener("click", () => { extModal.hidden = true; });
  }
  if (modalGotItBtn && extModal) {
    modalGotItBtn.addEventListener("click", () => { extModal.hidden = true; });
  }
  if (extModal) {
    extModal.addEventListener("click", (e) => {
      if (e.target === extModal) extModal.hidden = true;
    });
  }

  if (testConnBtn) {
    testConnBtn.addEventListener("click", async () => {
      connStatusText.textContent = "Connecting to MoodPulse...";
      connStatusText.style.color = "var(--text-muted)";
      try {
        const res = await fetch("/health");
        const d = await res.json();
        if (d.status === "ok") {
          connStatusText.textContent = "✓ Connected to server!";
          connStatusText.style.color = "#059669";
        }
      } catch (err) {
        connStatusText.textContent = "✕ Not reachable: " + err.message;
        connStatusText.style.color = "#dc2626";
      }
    });
  }

  // --- LOAD INITIAL HISTORY ON START ---
  async function loadHistory() {
    try {
      const res = await fetch("/api/history");
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      const data = await res.json();
      if (data.history) {
        renderHistory(data.history);
      }
      updateStatsDisplay(data.stats);
    } catch (err) {
      console.warn("Could not load history:", err);
    }
  }

  loadHistory();

  // Live Sync: auto-refresh timeline when returning to tab and every 8s while extension logs in background
  window.addEventListener("focus", () => {
    loadHistory();
  });
  setInterval(() => {
    loadHistory();
  }, 8000);
})();
