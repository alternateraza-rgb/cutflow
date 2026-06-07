const BRIDGE_URL = "http://127.0.0.1:8765";

const statusEl = document.querySelector("#status");
const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chat-form");
const promptEl = document.querySelector("#prompt");

async function checkBridge() {
  try {
    const response = await fetch(`${BRIDGE_URL}/health`);
    const payload = await response.json();
    const context = payload.context || {};
    statusEl.textContent = context.dry_run
      ? "Bridge online: dry run"
      : `Connected: ${context.project_name || "Resolve"}`;
    statusEl.classList.add("status--online");
    statusEl.classList.remove("status--offline");
  } catch (error) {
    statusEl.textContent = "Bridge offline";
    statusEl.classList.remove("status--online");
    statusEl.classList.add("status--offline");
  }
}

async function sendPrompt(prompt) {
  addMessage("user", "You", prompt);
  promptEl.value = "";

  try {
    const response = await fetch(`${BRIDGE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: prompt }),
    });
    const payload = await response.json();
    addMessage("assistant", "Cutflow", payload.reply || "Done.", {
      command: payload.command,
      result: payload.result,
    });
  } catch (error) {
    addMessage(
      "assistant",
      "Cutflow",
      "I could not reach the local bridge. Start it with: python bridge/server.py --dry-run",
      { error: String(error) },
    );
  }
}

function addMessage(role, author, text, debug) {
  const article = document.createElement("article");
  article.className = `message message--${role}`;

  const strong = document.createElement("strong");
  strong.textContent = author;
  article.appendChild(strong);

  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  article.appendChild(paragraph);

  if (debug) {
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(debug, null, 2);
    article.appendChild(pre);
  }

  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const prompt = promptEl.value.trim();
  if (prompt) {
    sendPrompt(prompt);
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    sendPrompt(button.dataset.prompt);
  });
});

checkBridge();
setInterval(checkBridge, 5000);
