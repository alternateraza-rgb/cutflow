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
    addMessage("assistant", "Cutflow", payload.reply || "Done.", payload, {
      command: payload.command,
      result: payload.result,
    });
  } catch (error) {
    addMessage(
      "assistant",
      "Cutflow",
      "I could not reach the local bridge. Start it with: python3 bridge/server.py --dry-run",
      null,
      { error: String(error) },
    );
  }
}

function addMessage(role, author, text, payload, debug) {
  const article = document.createElement("article");
  article.className = `message message--${role}`;

  const strong = document.createElement("strong");
  strong.textContent = author;
  article.appendChild(strong);

  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  article.appendChild(paragraph);

  const suggestions = payload?.result?.suggestions || [];
  if (suggestions.length > 0) {
    article.appendChild(renderSuggestions(suggestions));
  }

  if (debug) {
    const details = document.createElement("details");
    details.className = "debug-details";

    const summary = document.createElement("summary");
    summary.textContent = "Technical details";
    details.appendChild(summary);

    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(debug, null, 2);
    details.appendChild(pre);
    article.appendChild(details);
  }

  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderSuggestions(suggestions) {
  const section = document.createElement("section");
  section.className = "suggestions";
  section.setAttribute("aria-label", "Stock media suggestions");

  suggestions.forEach((item) => {
    const card = document.createElement("article");
    card.className = "suggestion-card";

    if (item.preview_url) {
      const image = document.createElement("img");
      image.src = item.preview_url;
      image.alt = item.title || "Stock media preview";
      image.loading = "lazy";
      card.appendChild(image);
    }

    const body = document.createElement("div");
    body.className = "suggestion-card__body";

    const title = document.createElement("h2");
    title.textContent = item.title || "Untitled result";
    body.appendChild(title);

    const meta = document.createElement("p");
    meta.textContent = [
      item.provider ? `Source: ${item.provider}` : null,
      item.type ? `Type: ${item.type}` : null,
      item.credit ? `Credit: ${item.credit}` : null,
    ]
      .filter(Boolean)
      .join(" • ");
    body.appendChild(meta);

    if (item.note) {
      const note = document.createElement("p");
      note.className = "suggestion-card__note";
      note.textContent = item.note;
      body.appendChild(note);
    }

    const actions = document.createElement("div");
    actions.className = "suggestion-card__actions";
    addLink(actions, "Open source", item.license_url || item.preview_url);
    addLink(actions, "Preview file", item.download_url);
    body.appendChild(actions);

    card.appendChild(body);
    section.appendChild(card);
  });

  return section;
}

function addLink(parent, label, url) {
  if (!url) {
    return;
  }
  const link = document.createElement("a");
  link.href = url;
  link.textContent = label;
  link.target = "_blank";
  link.rel = "noreferrer";
  parent.appendChild(link);
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
