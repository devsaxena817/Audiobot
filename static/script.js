// Elements
const audioFileInput = document.getElementById("audioFile");
const sendBtn = document.getElementById("sendBtn");
const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const chatBox = document.getElementById("chatBox");
const loadingEl = document.getElementById("loading");
const progressBar = document.getElementById("progressBar");
const player = document.getElementById("player");
const actions = document.getElementById("actions");
const downloadPdfBtn = document.getElementById("downloadPdfBtn");
const copyJsonBtn = document.getElementById("copyJsonBtn");
const toastBox = document.getElementById("toastBox");

let mediaRecorder, audioChunks = [];
let lastJson = null, lastPdfUrl = null;

// Toast
function toast(msg) {
    const t = document.createElement("div");
    t.className = "toast";
    t.innerText = msg;
    toastBox.appendChild(t);
    setTimeout(()=> t.remove(), 4500);
}

// Append message
function appendMessage(text, sender="bot") {
    const el = document.createElement("div");
    el.className = "msg " + (sender === "user" ? "user" : "bot");
    el.innerText = text;
    chatBox.appendChild(el);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Progress animation simulator
let progressInterval;
function startProgress() {
    loadingEl.classList.remove("hidden");
    progressBar.style.width = "0%";
    let w = 0;
    progressInterval = setInterval(()=>{
        w = Math.min(90, w + Math.random()*6);
        progressBar.style.width = w + "%";
    }, 300);
}
function stopProgress() {
    clearInterval(progressInterval);
    progressBar.style.width = "100%";
    setTimeout(()=> {
        loadingEl.classList.add("hidden");
        progressBar.style.width = "0%";
    }, 600);
}

// Send file to backend
async function sendAudioBlob(blob, filename="recording.wav") {
    appendMessage("Uploading audio...", "user");
    startProgress();
    const fd = new FormData();
    fd.append("audio", blob, filename);
    try {
        const res = await fetch("/process", { method: "POST", body: fd });
        const data = await res.json();
        stopProgress();

        if (data.error) {
            toast("Error: " + (data.error));
            appendMessage("Error: " + JSON.stringify(data.error));
            return;
        }

        lastJson = data.json;
        lastPdfUrl = data.pdf_url;
        // Show report text (human report)
        const human = data.report_text || "";
        appendMessage(human || (lastJson.summary || "No report text"), "bot");

        if (data.pdf_url) {
            actions.classList.remove("hidden");
            downloadPdfBtn.onclick = ()=> window.open(data.pdf_url, "_blank");
        }
    } catch (err) {
        stopProgress();
        toast("Network or server error");
        appendMessage("Network error: " + err.message);
    }
}

// Handle send file
sendBtn.onclick = () => {
    const f = audioFileInput.files[0];
    if (!f) { toast("Select an audio file first"); return; }
    appendMessage("File selected: " + f.name, "user");
    player.src = URL.createObjectURL(f);
    player.classList.remove("hidden");
    sendAudioBlob(f, f.name);
};

// Recording
recordBtn.onclick = async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = () => {
            const blob = new Blob(audioChunks, { type: "audio/webm" });
            player.src = URL.createObjectURL(blob);
            player.classList.remove("hidden");
            sendAudioBlob(blob, "recording.webm");
        };
        mediaRecorder.start();
        toast("Recording started");
        recordBtn.disabled = true;
        stopBtn.disabled = false;
    } catch(e) {
        toast("Microphone access denied");
    }
};

stopBtn.onclick = () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
        toast("Recording stopped");
    }
    recordBtn.disabled = false;
    stopBtn.disabled = true;
};

// Copy JSON
copyJsonBtn.onclick = () => {
    if (!lastJson) { toast("No JSON to copy"); return; }
    navigator.clipboard.writeText(JSON.stringify(lastJson, null, 2));
    toast("JSON copied to clipboard");
};
