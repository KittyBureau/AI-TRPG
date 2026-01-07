const input = document.getElementById("playerText");
const sendBtn = document.getElementById("sendBtn");
const log = document.getElementById("log");

function appendLine(label, text, isError) {
  const line = document.createElement("div");
  line.className = isError ? "line error" : "line";
  line.textContent = `${label}: ${text}`;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

async function sendTurn() {
  const text = input.value.trim();
  if (!text) {
    return;
  }

  appendLine("You", text, false);
  input.value = "";
  sendBtn.disabled = true;

  try {
    const response = await fetch("/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_text: text }),
    });

    const contentType = response.headers.get("content-type") || "";
    let data = null;
    if (contentType.includes("application/json")) {
      data = await response.json();
    } else {
      const raw = await response.text();
      data = { say: raw };
    }

    const say = data && typeof data.say === "string" ? data.say : "ERROR: Bad response";
    if (response.ok) {
      appendLine("GM", say, false);
    } else {
      appendLine("Error", say, true);
    }
  } catch (err) {
    appendLine("Error", String(err), true);
  } finally {
    sendBtn.disabled = false;
  }
}

sendBtn.addEventListener("click", sendTurn);
