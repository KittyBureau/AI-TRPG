const BASE_URL_KEY = "raw-console-base-url";

const elements = {
  campaignId: document.getElementById("campaignId"),
  reloadBtn: document.getElementById("reloadBtn"),
  statusLine: document.getElementById("statusLine"),
  currentArea: document.getElementById("currentArea"),
  reachableList: document.getElementById("reachableList"),
};

function setStatus(message) {
  elements.statusLine.textContent = message;
}

function getBaseUrl() {
  const raw = localStorage.getItem(BASE_URL_KEY) || "";
  return raw.trim().replace(/\/+$/, "");
}

function buildUrl(path) {
  const base = getBaseUrl();
  if (!base) {
    return path;
  }
  if (path.startsWith("/")) {
    return `${base}${path}`;
  }
  return `${base}/${path}`;
}

function setCurrentArea(area) {
  if (!area) {
    elements.currentArea.textContent = "-";
    return;
  }
  elements.currentArea.textContent = `${area.name} (${area.id})`;
}

function renderReachableAreas(areas) {
  elements.reachableList.innerHTML = "";
  if (!areas || !areas.length) {
    const item = document.createElement("li");
    item.textContent = "(none)";
    elements.reachableList.appendChild(item);
    return;
  }
  areas.forEach((area) => {
    const item = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = `${area.name} (${area.id})`;

    const moveBtn = document.createElement("button");
    moveBtn.type = "button";
    moveBtn.textContent = "Move";
    moveBtn.disabled = true;
    moveBtn.addEventListener("click", () => {
      console.log("Move clicked", area);
    });

    item.appendChild(label);
    item.appendChild(moveBtn);
    elements.reachableList.appendChild(item);
  });
}

async function loadMap() {
  const campaignId = elements.campaignId.value.trim();
  if (!campaignId) {
    setStatus("Campaign ID is required.");
    return;
  }
  const query = new URLSearchParams({ campaign_id: campaignId });
  const url = buildUrl(`/api/map/view?${query.toString()}`);

  setStatus("Loading...");
  try {
    const response = await fetch(url);
    if (!response.ok) {
      const text = await response.text();
      setCurrentArea(null);
      renderReachableAreas([]);
      setStatus(`Error ${response.status}: ${text}`);
      return;
    }
    const data = await response.json();
    setCurrentArea(data.current_area);
    renderReachableAreas(data.reachable_areas);
    setStatus(`Loaded: actor ${data.active_actor_id}`);
  } catch (error) {
    setCurrentArea(null);
    renderReachableAreas([]);
    setStatus(`Fetch error: ${error}`);
  }
}

function init() {
  elements.reloadBtn.addEventListener("click", loadMap);
  loadMap();
}

init();
