const input = document.getElementById("userText");
const generateBtn = document.getElementById("generateBtn");
const commentEl = document.getElementById("comment");
const statusEl = document.getElementById("status");
let lastComment = "";
const promptExample = document.getElementById("promptExample");

const exampleText =
  "Create a grounded detective with a quiet obsession, a single clear goal, " +
  "two practical strengths, one believable flaw, and a personal hook.";

promptExample.textContent = exampleText;

function setComment(text) {
  commentEl.textContent = text || "";
}

function setStatus(text) {
  statusEl.textContent = text || "";
}

function renderError(message) {
  setStatus(`ERROR: ${message}`);
}

async function postJSON(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const message = data && data.message ? data.message : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

async function renameAndSave(character, newName) {
  return postJSON("/api/characters/rename_and_save", {
    character,
    new_name: newName,
    comment: lastComment,
  });
}

async function handleGenerate() {
  const userText = input.value.trim();
  if (!userText) {
    renderError("Please enter some text.");
    return;
  }

  setStatus("");
  setComment("");
  generateBtn.disabled = true;
  try {
    const data = await postJSON("/api/characters/generate", { user_text: userText });
    if (data.status === "OK") {
      lastComment = data.comment || "";
      setComment(lastComment);
      setStatus(`Saved to ${data.saved_path}`);
      return;
    }
    if (data.status === "NAME_CONFLICT") {
      lastComment = data.comment || "";
      const newName = window.prompt(
        `Name '${data.conflict_name}' already exists. Enter a new name:`
      );
      if (!newName) {
        renderError("Rename cancelled.");
        return;
      }
      const renameResult = await renameAndSave(data.character, newName);
      if (renameResult.status === "OK") {
        setComment(renameResult.comment || lastComment);
        setStatus(`Saved to ${renameResult.saved_path}`);
        return;
      }
      if (renameResult.status === "NAME_CONFLICT") {
        renderError(`Name '${renameResult.conflict_name}' already exists.`);
        return;
      }
      setStatus("Unexpected response.");
      return;
    }
    setStatus("Unexpected response.");
  } catch (err) {
    renderError(String(err));
  } finally {
    generateBtn.disabled = false;
  }
}

generateBtn.addEventListener("click", handleGenerate);
