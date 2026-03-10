import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

class FakeElement {
  constructor(tagName, ownerDocument) {
    this.tagName = String(tagName || "div").toUpperCase();
    this.ownerDocument = ownerDocument;
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.listeners = new Map();
    this.className = "";
    this.textContent = "";
    this.value = "";
    this.rows = 0;
    this.selectionStart = null;
    this.selectionEnd = null;
    this._innerHTML = "";
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  setAttribute(name, value) {
    this.attributes.set(String(name), String(value));
  }

  getAttribute(name) {
    return this.attributes.has(String(name))
      ? this.attributes.get(String(name))
      : null;
  }

  addEventListener(type, handler) {
    const key = String(type);
    const listeners = this.listeners.get(key) || [];
    listeners.push(handler);
    this.listeners.set(key, listeners);
  }

  dispatchEvent(event) {
    const type = event && typeof event.type === "string" ? event.type : "";
    const listeners = this.listeners.get(type) || [];
    const dispatched = { ...event, target: this, currentTarget: this };
    for (const listener of listeners) {
      listener(dispatched);
    }
    return true;
  }

  focus() {
    this.ownerDocument.activeElement = this;
  }

  setSelectionRange(start, end) {
    this.selectionStart = start;
    this.selectionEnd = end;
  }

  contains(node) {
    if (node === this) {
      return true;
    }
    return this.children.some((child) => child.contains(node));
  }

  querySelector(selector) {
    const focusKeyMatch = /^\[data-focus-key="(.+)"\]$/.exec(selector);
    if (focusKeyMatch) {
      const focusKey = focusKeyMatch[1];
      return walk(this, (node) => node.getAttribute("data-focus-key") === focusKey);
    }
    return null;
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    this.children = [];
  }
}

class FakeDocument {
  constructor() {
    this.activeElement = null;
    this.elementsById = new Map();
  }

  createElement(tagName) {
    return new FakeElement(tagName, this);
  }

  getElementById(id) {
    return this.elementsById.get(String(id)) || null;
  }

  registerElement(id, element) {
    element.setAttribute("id", id);
    this.elementsById.set(String(id), element);
    return element;
  }
}

function walk(root, predicate) {
  if (predicate(root)) {
    return root;
  }
  for (const child of root.children) {
    const result = walk(child, predicate);
    if (result) {
      return result;
    }
  }
  return null;
}

function findButtonByText(root, text) {
  return walk(root, (node) => node.tagName === "BUTTON" && node.textContent === text);
}

function flushMicrotasks() {
  return Promise.resolve().then(() => Promise.resolve());
}

async function loadCharacterLibraryPanelModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/panels/character_library_panel.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

function createStore(overrides = {}) {
  const state = {
    baseUrl: "http://127.0.0.1:8000",
    campaignId: "camp_001",
    statusMessage: "",
    character: {
      library: [],
      error: null,
      create_form: {
        name: "",
        summary: "",
        tags: "",
      },
    },
    ...overrides.state,
  };
  const listeners = new Set();
  const calls = {
    loadCharacterToCampaign: [],
  };
  const store = {
    getState() {
      return state;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    emit() {
      for (const listener of listeners) {
        listener();
      }
    },
    setCharacterCreateForm(patch) {
      state.character.create_form = {
        ...state.character.create_form,
        ...patch,
      };
      store.emit();
    },
    async loadCharacterLibrary() {
      return {
        ok: true,
        status: 200,
        data: state.character.library,
      };
    },
    async createCharacter() {
      return {
        ok: true,
        status: 200,
        data: { character_id: "pc_created" },
      };
    },
    async loadCharacterToCampaign(campaignId, characterId, baseUrl) {
      calls.loadCharacterToCampaign.push({ campaignId, characterId, baseUrl });
      return {
        ok: true,
        status: 200,
        data: { campaign_id: campaignId, character_id: characterId },
      };
    },
    setStatusMessage(message) {
      state.statusMessage = message;
      store.emit();
    },
    setDebugResponseText() {},
    calls,
  };
  return store;
}

test("Character Library keeps the same focused input while typing through store rerenders", async () => {
  const { initPanel } = await loadCharacterLibraryPanelModule();
  const document = new FakeDocument();
  const mount = document.registerElement(
    "characterLibraryPanel",
    document.createElement("section")
  );

  global.document = document;
  global.HTMLElement = FakeElement;

  const store = createStore();
  initPanel(store);
  await flushMicrotasks();

  const nameInput = mount.querySelector('[data-focus-key="character-name"]');
  assert.ok(nameInput);

  nameInput.focus();
  nameInput.value = "Scout";
  nameInput.setSelectionRange(5, 5);
  nameInput.dispatchEvent({ type: "input" });

  const rerenderedInput = mount.querySelector('[data-focus-key="character-name"]');
  assert.equal(rerenderedInput, nameInput);
  assert.equal(document.activeElement, nameInput);
  assert.equal(nameInput.value, "Scout");
  assert.equal(store.getState().character.create_form.name, "Scout");
});

test("Character Library preserves typed value and focus across unrelated refresh rerenders", async () => {
  const { initPanel } = await loadCharacterLibraryPanelModule();
  const document = new FakeDocument();
  const mount = document.registerElement(
    "characterLibraryPanel",
    document.createElement("section")
  );

  global.document = document;
  global.HTMLElement = FakeElement;

  const store = createStore();
  initPanel(store);
  await flushMicrotasks();

  const nameInput = mount.querySelector('[data-focus-key="character-name"]');
  nameInput.focus();
  nameInput.value = "Marshal";
  nameInput.dispatchEvent({ type: "input" });

  store.getState().character.library = [
    { id: "pc_001", name: "Scout", summary: "Quiet observer", tags: ["stealth"] },
  ];
  store.emit();

  assert.equal(mount.querySelector('[data-focus-key="character-name"]'), nameInput);
  assert.equal(document.activeElement, nameInput);
  assert.equal(nameInput.value, "Marshal");
});

test("Character Library still loads a library entry into the current campaign", async () => {
  const { initPanel } = await loadCharacterLibraryPanelModule();
  const document = new FakeDocument();
  const mount = document.registerElement(
    "characterLibraryPanel",
    document.createElement("section")
  );

  global.document = document;
  global.HTMLElement = FakeElement;

  const store = createStore({
    state: {
      character: {
        library: [
          { id: "pc_001", name: "Scout", summary: "Quiet observer", tags: ["stealth"] },
        ],
        error: null,
        create_form: {
          name: "",
          summary: "",
          tags: "",
        },
      },
    },
  });
  initPanel(store);
  await flushMicrotasks();

  const loadButton = findButtonByText(mount, "Load to Campaign");
  assert.ok(loadButton);

  loadButton.dispatchEvent({ type: "click" });
  await flushMicrotasks();

  assert.deepEqual(store.calls.loadCharacterToCampaign, [
    {
      campaignId: "camp_001",
      characterId: "pc_001",
      baseUrl: "http://127.0.0.1:8000",
    },
  ]);
});
