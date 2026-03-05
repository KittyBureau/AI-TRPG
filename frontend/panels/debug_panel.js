export function initPanel(store) {
  const mount = document.getElementById("debugPanel");
  if (!mount) {
    return;
  }

  function render() {
    const state = store.getState();
    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Debug";
    mount.appendChild(title);

    const status = document.createElement("div");
    status.className = "row";
    status.textContent = `Status: ${state.statusMessage || "Idle"}`;
    mount.appendChild(status);

    const actions = document.createElement("div");
    actions.className = "inline";
    const clear = document.createElement("button");
    clear.textContent = "Clear Response";
    clear.addEventListener("click", () => {
      store.setDebugResponseText("");
    });
    actions.appendChild(clear);
    mount.appendChild(actions);

    const pre = document.createElement("pre");
    pre.className = "raw";
    pre.textContent = state.debug?.responseText || "No API response yet.";
    mount.appendChild(pre);
  }

  render();
  store.subscribe(render);
}
