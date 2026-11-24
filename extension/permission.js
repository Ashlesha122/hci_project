const requestBtn = document.getElementById("request-btn");
const promptDesc = document.getElementById("prompt-desc");
const successBox = document.getElementById("success-box");
const errorBox = document.getElementById("error-box");

async function askCamera() {
  errorBox.style.display = "none";
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    // Stop tracks immediately since we only needed the permission grant
    stream.getTracks().forEach((track) => track.stop());

    requestBtn.style.display = "none";
    promptDesc.style.display = "none";
    successBox.style.display = "block";

    // Auto-close after 1.8 seconds so the user is seamlessly returned to their work
    setTimeout(() => {
      try {
        window.close();
      } catch (_) {}
    }, 1800);
  } catch (err) {
    console.error("Camera permission error:", err);
    errorBox.style.display = "block";
  }
}

if (requestBtn) {
  requestBtn.addEventListener("click", askCamera);
}

// Automatically trigger on page load so the Chrome prompt appears immediately
document.addEventListener("DOMContentLoaded", () => {
  askCamera();
});
