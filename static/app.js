let currentProjectId = null;
let segmentation = null;
let locked = false;

const titleInput = document.querySelector("#titleInput");
const storyInput = document.querySelector("#storyInput");
const segmentButton = document.querySelector("#segmentButton");
const saveButton = document.querySelector("#saveButton");
const confirmButton = document.querySelector("#confirmButton");
const colabJobButton = document.querySelector("#colabJobButton");
const projectStatus = document.querySelector("#projectStatus");
const summary = document.querySelector("#summary");
const jobStatus = document.querySelector("#jobStatus");
const charactersEditor = document.querySelector("#charactersEditor");
const scenesEditor = document.querySelector("#scenesEditor");

segmentButton.addEventListener("click", segmentStory);
saveButton.addEventListener("click", saveDraft);
confirmButton.addEventListener("click", confirmSegmentation);
colabJobButton.addEventListener("click", prepareColabJob);

async function segmentStory() {
  const title = titleInput.value.trim() || "Untitled Story";
  const story = storyInput.value.trim();

  if (!story) {
    alert("Please paste a story first.");
    return;
  }

  setBusy(segmentButton, "Segmenting...");

  try {
    const response = await fetch("/api/projects/segment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, story }),
    });

    if (!response.ok) {
      throw new Error(await readError(response));
    }

    const result = await response.json();
    currentProjectId = result.project_id;
    segmentation = result.segmentation;
    locked = false;
    hideJobStatus();
    render();
  } catch (error) {
    alert(error.message);
  } finally {
    clearBusy(segmentButton, "Segment Story");
  }
}

async function saveDraft() {
  if (!currentProjectId || !segmentation || locked) return;

  collectEditorData();
  setBusy(saveButton, "Saving...");

  try {
    const response = await fetch(`/api/projects/${currentProjectId}/segmentation`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(segmentation),
    });

    if (!response.ok) {
      throw new Error(await readError(response));
    }

    const result = await response.json();
    segmentation = result.segmentation;
    locked = result.locked;
    renderStatus();
  } catch (error) {
    alert(error.message);
  } finally {
    clearBusy(saveButton, "Save Draft");
  }
}

async function confirmSegmentation() {
  if (!currentProjectId || !segmentation || locked) return;

  collectEditorData();
  setBusy(confirmButton, "Confirming...");

  try {
    const response = await fetch(`/api/projects/${currentProjectId}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(segmentation),
    });

    if (!response.ok) {
      throw new Error(await readError(response));
    }

    const result = await response.json();
    segmentation = result.segmentation;
    locked = result.locked;
    hideJobStatus();
    render();
  } catch (error) {
    alert(error.message);
  } finally {
    clearBusy(confirmButton, "Confirm Segmentation");
  }
}

async function prepareColabJob() {
  if (!currentProjectId || !locked) return;

  setBusy(colabJobButton, "Preparing...");

  try {
    const response = await fetch(`/api/projects/${currentProjectId}/colab-job`, {
      method: "POST",
    });

    if (!response.ok) {
      throw new Error(await readError(response));
    }

    const result = await response.json();
    jobStatus.classList.remove("hidden");
    jobStatus.innerHTML = `
      <strong>Colab job ready:</strong> ${escapeHtml(result.job_id)}<br>
      <strong>Folder:</strong> ${escapeHtml(result.job_path)}<br>
      <strong>Input JSON:</strong> ${escapeHtml(result.segmentation_path)}
    `;
  } catch (error) {
    alert(error.message);
  } finally {
    clearBusy(colabJobButton, "Prepare Colab Job");
  }
}

function render() {
  renderStatus();
  renderSummary();
  renderCharacters();
  renderScenes();

  const hasProject = Boolean(currentProjectId && segmentation);
  saveButton.disabled = !hasProject || locked;
  confirmButton.disabled = !hasProject || locked;
  colabJobButton.disabled = !hasProject || !locked;
}

function renderStatus() {
  if (!currentProjectId) {
    projectStatus.textContent = "No project";
    return;
  }

  projectStatus.textContent = locked
    ? `Project ${currentProjectId}: locked`
    : `Project ${currentProjectId}: draft`;
}

function renderSummary() {
  if (!segmentation) {
    summary.textContent = "Add a story and click Segment Story.";
    return;
  }

  const sceneCount = segmentation.scenes.length;
  const characterCount = segmentation.characters.length;
  const dialogueCount = segmentation.scenes.reduce((total, scene) => total + scene.dialogues.length, 0);
  summary.textContent = `${sceneCount} scenes, ${characterCount} characters, ${dialogueCount} dialogues detected.`;
}

function renderCharacters() {
  charactersEditor.innerHTML = "";
  if (!segmentation) return;

  const header = document.createElement("div");
  header.className = "section-title-row";
  header.innerHTML = "<h2>Characters</h2>";

  const addButton = document.createElement("button");
  addButton.className = "secondary-button";
  addButton.textContent = "Add Character";
  addButton.disabled = locked;
  addButton.addEventListener("click", () => {
    segmentation.characters.push({
      id: createId("char"),
      name: "",
      role: "",
      description: "",
    });
    renderCharacters();
  });

  header.appendChild(addButton);
  charactersEditor.appendChild(header);

  segmentation.characters.forEach((character, index) => {
    const node = document.querySelector("#characterTemplate").content.cloneNode(true);
    const row = node.querySelector(".character-row");
    bindInput(row, "name", character.name, value => character.name = value);
    bindInput(row, "role", character.role, value => character.role = value);
    bindInput(row, "description", character.description, value => character.description = value);

    row.querySelector("[data-action='remove-character']").addEventListener("click", () => {
      segmentation.characters.splice(index, 1);
      renderCharacters();
    });

    setDisabled(row, locked);
    charactersEditor.appendChild(row);
  });
}

function renderScenes() {
  scenesEditor.innerHTML = "";
  if (!segmentation) return;

  const header = document.createElement("div");
  header.className = "section-title-row";
  header.innerHTML = "<h2>Scenes</h2>";

  const addButton = document.createElement("button");
  addButton.className = "secondary-button";
  addButton.textContent = "Add Scene";
  addButton.disabled = locked;
  addButton.addEventListener("click", () => {
    segmentation.scenes.push({
      id: createId("scene"),
      scene_number: segmentation.scenes.length + 1,
      title: `Scene ${segmentation.scenes.length + 1}`,
      location: "",
      narration: "",
      characters: [],
      dialogues: [],
      notes: "",
    });
    renderScenes();
    renderSummary();
  });

  header.appendChild(addButton);
  scenesEditor.appendChild(header);

  segmentation.scenes.forEach((scene, sceneIndex) => {
    const node = document.querySelector("#sceneTemplate").content.cloneNode(true);
    const card = node.querySelector(".scene-card");

    bindInput(card, "title", scene.title, value => scene.title = value);
    bindInput(card, "location", scene.location, value => scene.location = value);
    bindInput(card, "narration", scene.narration, value => scene.narration = value);
    bindInput(card, "characters", scene.characters.join(", "), value => {
      scene.characters = value.split(",").map(item => item.trim()).filter(Boolean);
    });

    const dialoguesContainer = card.querySelector(".dialogues");
    scene.dialogues.forEach((dialogue, dialogueIndex) => {
      dialoguesContainer.appendChild(renderDialogue(scene, dialogue, dialogueIndex));
    });

    card.querySelector("[data-action='add-dialogue']").addEventListener("click", () => {
      scene.dialogues.push({ id: createId("dlg"), speaker: "", text: "" });
      renderScenes();
      renderSummary();
    });

    card.querySelector("[data-action='remove-scene']").addEventListener("click", () => {
      segmentation.scenes.splice(sceneIndex, 1);
      renumberScenes();
      renderScenes();
      renderSummary();
    });

    setDisabled(card, locked);
    scenesEditor.appendChild(card);
  });
}

function renderDialogue(scene, dialogue, dialogueIndex) {
  const node = document.querySelector("#dialogueTemplate").content.cloneNode(true);
  const row = node.querySelector(".dialogue-row");

  bindInput(row, "speaker", dialogue.speaker, value => dialogue.speaker = value);
  bindInput(row, "text", dialogue.text, value => dialogue.text = value);

  row.querySelector("[data-action='remove-dialogue']").addEventListener("click", () => {
    scene.dialogues.splice(dialogueIndex, 1);
    renderScenes();
    renderSummary();
  });

  return row;
}

function collectEditorData() {
  renumberScenes();
}

function renumberScenes() {
  segmentation.scenes.forEach((scene, index) => {
    scene.scene_number = index + 1;
  });
}

function bindInput(root, field, value, onChange) {
  const input = root.querySelector(`[data-field="${field}"]`);
  input.value = value || "";
  input.addEventListener("input", event => {
    onChange(event.target.value);
    renderSummary();
  });
}

function setDisabled(root, disabled) {
  root.querySelectorAll("input, textarea, button").forEach(element => {
    element.disabled = disabled;
  });
}

function setBusy(button, text) {
  button.dataset.originalText = button.textContent;
  button.textContent = text;
  button.disabled = true;
}

function clearBusy(button, fallbackText) {
  button.textContent = button.dataset.originalText || fallbackText;
  button.disabled = false;
  render();
}

async function readError(response) {
  try {
    const data = await response.json();
    return data.detail || "Request failed.";
  } catch {
    return "Request failed.";
  }
}

function createId(prefix) {
  return `${prefix}_${Math.random().toString(16).slice(2, 12)}`;
}

function hideJobStatus() {
  jobStatus.classList.add("hidden");
  jobStatus.textContent = "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
