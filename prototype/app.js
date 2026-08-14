(() => {
  "use strict";

  const FALLBACK_PROVIDERS = [
    {
      id: "openai",
      name: "OpenAI",
      defaultModel: "gpt-5.6-terra",
      configured: false,
      models: [
        { id: "gpt-5.6-terra", name: "GPT-5.6 Terra", note: "Balanced" },
        { id: "gpt-5.6-sol", name: "GPT-5.6 Sol", note: "Highest quality" },
        { id: "gpt-5.6-luna", name: "GPT-5.6 Luna", note: "Economical" },
      ],
    },
    {
      id: "gemini",
      name: "Google Gemini",
      defaultModel: "gemini-3.6-flash",
      configured: false,
      models: [
        { id: "gemini-3.6-flash", name: "Gemini 3.6 Flash", note: "Balanced" },
        { id: "gemini-3.1-pro-preview", name: "Gemini 3.1 Pro Preview", note: "Quality" },
        { id: "gemini-3.5-flash-lite", name: "Gemini 3.5 Flash-Lite", note: "Economical" },
      ],
    },
  ];

  const state = {
    tool: "select",
    scale: 1,
    panX: 80,
    panY: 70,
    assets: [],
    selected: null,
    selectedAssetIds: [],
    selectedAnnotationIds: [],
    isSpaceDown: false,
    interaction: null,
    annotationCounter: 0,
    aiDraft: null,
    draftController: null,
    draftRequestId: 0,
    lastDraftError: "",
    providerModel: "gpt-5.6-terra",
    providerModels: { openai: "gpt-5.6-terra", gemini: "gemini-3.6-flash" },
    providerId: "openai",
    imageDetail: "auto",
    exportPreferences: { copyPrompt: true, openFolder: true },
    workspacePreferences: { lastActiveProjectId: null, openProjectIds: [] },
    workspaceTabsInitialized: false,
    preferencesSaveTimer: null,
    providers: cloneProviderRegistry(FALLBACK_PROVIDERS),
    mockMode: false,
    projects: [],
    currentProject: null,
    closedProjectIds: new Set(),
    renamingProjectId: null,
    folderSaveTimer: null,
    history: { past: [], future: [], limit: 80 },
    saveTimer: null,
    database: null,
  };

  const els = {
    shell: document.querySelector(".app-shell"),
    workspace: document.querySelector("#workspace"),
    scene: document.querySelector("#scene"),
    emptyState: document.querySelector("#emptyState"),
    modeHint: document.querySelector("#modeHint"),
    fileInput: document.querySelector("#fileInput"),
    emptyImportButton: document.querySelector("#emptyImportButton"),
    fitButton: document.querySelector("#fitButton"),
    undoButton: document.querySelector("#undoButton"),
    redoButton: document.querySelector("#redoButton"),
    clearButton: document.querySelector("#clearButton"),
    settingsButton: document.querySelector("#settingsButton"),
    exportButton: document.querySelector("#exportButton"),
    previewButton: document.querySelector("#previewButton"),
    mockDraftButton: document.querySelector("#mockDraftButton"),
    aiSettings: document.querySelector("#aiSettings"),
    providerStatus: document.querySelector("#providerStatus"),
    providerInput: document.querySelector("#providerInput"),
    modelInput: document.querySelector("#modelInput"),
    imageDetailInput: document.querySelector("#imageDetailInput"),
    apiKeyInput: document.querySelector("#apiKeyInput"),
    keyHint: document.querySelector("#keyHint"),
    saveProviderButton: document.querySelector("#saveProviderButton"),
    removeProviderButton: document.querySelector("#removeProviderButton"),
    copyPromptOnExportInput: document.querySelector("#copyPromptOnExportInput"),
    openFolderOnExportInput: document.querySelector("#openFolderOnExportInput"),
    panel: document.querySelector("#panel"),
    collapsePanelButton: document.querySelector("#collapsePanelButton"),
    expandPanelButton: document.querySelector("#expandPanelButton"),
    objectiveInput: document.querySelector("#objectiveInput"),
    formatInput: document.querySelector("#formatInput"),
    referenceList: document.querySelector("#referenceList"),
    cropCount: document.querySelector("#cropCount"),
    promptOutputBlock: document.querySelector("#promptOutputBlock"),
    promptOutput: document.querySelector("#promptOutput"),
    promptStatus: document.querySelector("#promptStatus"),
    promptErrorActions: document.querySelector("#promptErrorActions"),
    retryDraftButton: document.querySelector("#retryDraftButton"),
    regeneratePromptButton: document.querySelector("#regeneratePromptButton"),
    restorePromptButton: document.querySelector("#restorePromptButton"),
    copyPromptButton: document.querySelector("#copyPromptButton"),
    promptTab: document.querySelector("#promptTab"),
    selectionTab: document.querySelector("#selectionTab"),
    projectsTab: document.querySelector("#projectsTab"),
    settingsTab: document.querySelector("#settingsTab"),
    selectionEmpty: document.querySelector("#selectionEmpty"),
    selectionDetails: document.querySelector("#selectionDetails"),
    statusText: document.querySelector("#statusText"),
    saveText: document.querySelector("#saveText"),
    zoomText: document.querySelector("#zoomText"),
    projectTabs: document.querySelector("#projectTabs"),
    topCreateProjectButton: document.querySelector("#topCreateProjectButton"),
    openProjectsButton: document.querySelector("#openProjectsButton"),
    currentProjectName: document.querySelector("#currentProjectName"),
    projectsFolderPath: document.querySelector("#projectsFolderPath"),
    newProjectNameInput: document.querySelector("#newProjectNameInput"),
    createProjectButton: document.querySelector("#createProjectButton"),
    saveProjectButton: document.querySelector("#saveProjectButton"),
    refreshProjectsButton: document.querySelector("#refreshProjectsButton"),
    projectList: document.querySelector("#projectList"),
    providerConnection: document.querySelector("#providerConnection"),
    providerConnectionTitle: document.querySelector("#providerConnectionTitle"),
  };

  function cloneProviderRegistry(providers) {
    return providers.map((provider) => ({ ...provider, models: provider.models.map((model) => ({ ...model })) }));
  }

  const DB_NAME = "ai-canvas-prototype";
  const DB_STORE = "projects";
  const DB_KEY = "default-project";

  function uid(prefix) {
    return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function formatDuration(seconds) {
    const value = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(value / 60);
    const remaining = Math.floor(value % 60);
    return `${minutes}:${String(remaining).padStart(2, "0")}`;
  }

  function titleCase(value) {
    return value
      .trim()
      .replace(/[-_]+/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function annotationLetter(index) {
    let value = index + 1;
    let result = "";
    while (value > 0) {
      value -= 1;
      result = String.fromCharCode(65 + (value % 26)) + result;
      value = Math.floor(value / 26);
    }
    return result;
  }

  function nextReferenceNumber() {
    return state.assets.reduce((maximum, asset) => Math.max(maximum, asset.referenceNumber || 0), 0) + 1;
  }

  function slugify(value) {
    return value
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 36) || "reference";
  }

  function parseInstruction(raw) {
    const normalized = raw.trim().replace(/\s+/g, " ");
    const split = normalized.match(/^(.*?)(?:\s+(?:without|no|exclude|excluding|remove|ignore)\s+)(.+)$/i);
    const subject = (split?.[1] || normalized || "reference").trim().replace(/[\s,;:.]+$/g, "");
    const excluded = (split?.[2] || "").trim().replace(/[\s,;:.]+$/g, "");
    const label = titleCase(subject.replace(/^(use|keep|take|match|reference)\s+/i, ""));
    const description = `A focused crop corresponding to the instruction: ${normalized}`;
    const use = normalized;
    const avoid = excluded ? `Do not include or reproduce ${excluded}.` : "";
    return { label: label || "Reference", description, use, avoid };
  }

  function setStatus(message) {
    els.statusText.textContent = message;
  }

  function clone(value) {
    return window.structuredClone ? window.structuredClone(value) : JSON.parse(JSON.stringify(value));
  }

  function captureSnapshot() {
    return {
      assets: clone(state.assets),
      selected: clone(state.selected),
      selectedAssetIds: clone(state.selectedAssetIds),
      selectedAnnotationIds: clone(state.selectedAnnotationIds),
      panX: state.panX,
      panY: state.panY,
      scale: state.scale,
      annotationCounter: state.annotationCounter,
      aiDraft: clone(state.aiDraft),
      providerModel: els.modelInput.value || state.providerModel,
      providerModels: { ...state.providerModels, [els.providerInput.value]: els.modelInput.value },
      providerId: els.providerInput.value || state.providerId,
      imageDetail: els.imageDetailInput.value || state.imageDetail,
      objective: els.objectiveInput.value,
      format: els.formatInput.value,
    };
  }

  function snapshotsDiffer(left, right) {
    return JSON.stringify(left) !== JSON.stringify(right);
  }

  function updateHistoryButtons() {
    els.undoButton.disabled = state.history.past.length === 0;
    els.redoButton.disabled = state.history.future.length === 0;
  }

  function draftFingerprint() {
    return JSON.stringify({
      objective: els.objectiveInput.value.trim(),
      draftingInstructions: els.formatInput.value.trim(),
      provider: els.providerInput.value,
      model: els.modelInput.value,
      imageDetail: els.imageDetailInput.value,
      references: getCompiledReferences().map(({ asset, annotation, filename }) => ({
        filename,
        assetId: asset.id,
        annotationId: annotation.id,
        instruction: annotation.rawInstruction,
        region: [annotation.x, annotation.y, annotation.width, annotation.height],
      })),
      videos: getCompiledVideoReferences().map(({ asset, filename, instruction }) => ({
        filename,
        assetId: asset.id,
        instruction,
        duration: asset.duration,
      })),
    });
  }

  function normalizeDraft(draft) {
    if (!draft?.finalPrompt) return null;
    const finalPrompt = String(draft.finalPrompt);
    return {
      ...draft,
      finalPrompt,
      originalPrompt: String(draft.originalPrompt || finalPrompt),
      edited: Boolean(draft.edited || finalPrompt !== String(draft.originalPrompt || finalPrompt)),
      stale: Boolean(draft.stale),
      fingerprint: draft.fingerprint || null,
    };
  }

  function renderPromptState() {
    const draft = normalizeDraft(state.aiDraft);
    state.aiDraft = draft;
    if (!draft) {
      els.promptOutputBlock.hidden = !state.lastDraftError;
      els.promptOutput.value = "";
      els.promptStatus.textContent = state.lastDraftError || "";
      els.promptStatus.className = `prompt-status${state.lastDraftError ? " error" : ""}`;
      els.promptErrorActions.hidden = !state.lastDraftError;
      els.restorePromptButton.disabled = true;
      return;
    }
    els.promptOutputBlock.hidden = false;
    if (els.promptOutput.value !== draft.finalPrompt) els.promptOutput.value = draft.finalPrompt;
    els.restorePromptButton.disabled = draft.finalPrompt === draft.originalPrompt;
    els.promptErrorActions.hidden = !state.lastDraftError;
    if (state.lastDraftError) {
      els.promptStatus.textContent = state.lastDraftError;
      els.promptStatus.className = "prompt-status error";
    } else if (draft.stale) {
      els.promptStatus.textContent = draft.staleReason || "References or instructions changed. Regenerate before exporting.";
      els.promptStatus.className = "prompt-status warning";
    } else if (draft.edited) {
      els.promptStatus.textContent = "Edited manually. Your changes are saved and will be exported.";
      els.promptStatus.className = "prompt-status";
    } else {
      const source = draft.source === "vision-model" ? `${draft.provider || "AI"} / ${draft.model}` : "local draft";
      els.promptStatus.textContent = `Current with canvas · ${source}`;
      els.promptStatus.className = "prompt-status";
    }
  }

  function invalidateAIDraft(reason = "References or instructions changed. Regenerate before exporting.") {
    if (!state.aiDraft) return;
    state.aiDraft.stale = true;
    state.aiDraft.staleReason = reason;
    renderPromptState();
  }

  function pushHistory(snapshot, { preserveDraft = false } = {}) {
    if (!preserveDraft) invalidateAIDraft();
    if (!snapshot || !snapshotsDiffer(snapshot, captureSnapshot())) return false;
    state.history.past.push(snapshot);
    if (state.history.past.length > state.history.limit) state.history.past.shift();
    state.history.future = [];
    updateHistoryButtons();
    scheduleSave();
    return true;
  }

  function applySnapshot(snapshot, { save = true, preserveProviderSettings = false } = {}) {
    state.assets = clone(snapshot.assets || []);
    state.assets.forEach((asset) => {
      asset.type = asset.type || "image";
      asset.annotations = asset.annotations || [];
      asset.annotations.forEach((annotation) => delete annotation.role);
      if (asset.type === "video") {
        asset.videoInstruction = asset.videoInstruction || "";
        asset.videoObservations = asset.videoObservations || [];
      }
    });
    state.selected = clone(snapshot.selected || null);
    state.selectedAssetIds = clone(snapshot.selectedAssetIds || []);
    state.selectedAnnotationIds = clone(snapshot.selectedAnnotationIds || []);
    state.panX = Number.isFinite(snapshot.panX) ? snapshot.panX : 80;
    state.panY = Number.isFinite(snapshot.panY) ? snapshot.panY : 70;
    state.scale = Number.isFinite(snapshot.scale) ? snapshot.scale : 1;
    state.annotationCounter = snapshot.annotationCounter || 0;
    state.aiDraft = normalizeDraft(clone(snapshot.aiDraft || null));
    state.lastDraftError = "";
    if (!preserveProviderSettings) {
      state.providerId = snapshot.providerId || "openai";
      state.providerModels = {
        openai: "gpt-5.6-terra",
        gemini: "gemini-3.6-flash",
        ...(snapshot.providerModels || {}),
      };
      if (snapshot.providerModel) state.providerModels[state.providerId] = snapshot.providerModel;
      state.providerModel = state.providerModels[state.providerId];
      state.imageDetail = snapshot.imageDetail || "auto";
      els.providerInput.value = state.providerId;
      renderProviderSettings();
      els.imageDetailInput.value = state.imageDetail;
    }
    els.objectiveInput.value = snapshot.objective || "";
    els.formatInput.value = snapshot.format || "";
    renderAll();
    if (state.aiDraft?.fingerprint && state.aiDraft.fingerprint !== draftFingerprint()) {
      state.aiDraft.stale = true;
      state.aiDraft.staleReason = "This saved prompt no longer matches the current references.";
    }
    renderPromptState();
    if (save) scheduleSave();
  }

  function undo() {
    const snapshot = state.history.past.pop();
    if (!snapshot) return;
    state.history.future.push(captureSnapshot());
    applySnapshot(snapshot);
    updateHistoryButtons();
    setStatus("Undid last change");
  }

  function redo() {
    const snapshot = state.history.future.pop();
    if (!snapshot) return;
    state.history.past.push(captureSnapshot());
    applySnapshot(snapshot);
    updateHistoryButtons();
    setStatus("Redid last change");
  }

  function openProjectDatabase() {
    if (state.database) return Promise.resolve(state.database);
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(DB_STORE)) {
          request.result.createObjectStore(DB_STORE);
        }
      };
      request.onsuccess = () => {
        state.database = request.result;
        resolve(request.result);
      };
      request.onerror = () => reject(request.error);
    });
  }

  async function saveProjectNow() {
    if (new URLSearchParams(window.location.search).has("benchmark")) return;
    try {
      const database = await openProjectDatabase();
      await new Promise((resolve, reject) => {
        const transaction = database.transaction(DB_STORE, "readwrite");
        transaction.objectStore(DB_STORE).put(captureSnapshot(), DB_KEY);
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
      });
      els.saveText.textContent = "Saved locally";
    } catch (error) {
      console.error(error);
      els.saveText.textContent = "Local save failed";
    }
  }

  function scheduleSave() {
    if (new URLSearchParams(window.location.search).has("benchmark")) return;
    els.saveText.textContent = "Saving…";
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(saveProjectNow, 250);
    clearTimeout(state.folderSaveTimer);
    if (state.currentProject) {
      state.folderSaveTimer = setTimeout(() => saveCurrentProject({ quiet: true, refresh: false }), 900);
    }
  }

  async function restoreProject() {
    try {
      const database = await openProjectDatabase();
      const snapshot = await new Promise((resolve, reject) => {
        const transaction = database.transaction(DB_STORE, "readonly");
        const request = transaction.objectStore(DB_STORE).get(DB_KEY);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      if (snapshot) {
        applySnapshot(snapshot, { save: false });
        els.saveText.textContent = "Restored locally";
        setStatus("Project restored");
        return true;
      }
      els.saveText.textContent = "Saved locally";
    } catch (error) {
      console.error(error);
      els.saveText.textContent = "Local save unavailable";
    }
    return false;
  }

  function setTool(tool) {
    state.tool = tool;
    document.querySelectorAll(".tool[data-tool]").forEach((button) => {
      button.classList.toggle("active", button.dataset.tool === tool);
    });
    els.workspace.classList.toggle("tool-region", tool === "region");
    els.workspace.classList.toggle("tool-hand", tool === "hand");
    els.modeHint.hidden = tool !== "region";
    setStatus(tool === "region" ? "Draw a region on an image" : "Ready");
  }

  function renderTransform() {
    els.scene.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.scale})`;
    els.scene.style.setProperty("--inverse-scale", String(1 / state.scale));
    const gridSize = Math.max(8, 20 * state.scale);
    els.workspace.style.backgroundSize = `${gridSize}px ${gridSize}px`;
    els.workspace.style.backgroundPosition = `${state.panX % gridSize}px ${state.panY % gridSize}px`;
    els.zoomText.textContent = `${Math.round(state.scale * 100)}%`;
  }

  function screenToWorld(clientX, clientY) {
    const rect = els.workspace.getBoundingClientRect();
    return {
      x: (clientX - rect.left - state.panX) / state.scale,
      y: (clientY - rect.top - state.panY) / state.scale,
    };
  }

  function updateEmptyState() {
    els.emptyState.hidden = state.assets.length > 0;
  }

  function loadImageFile(file) {
    if (file.type.startsWith("video/")) {
      loadVideoFile(file);
      return;
    }
    if (!file.type.startsWith("image/")) return;
    const reader = new FileReader();
    reader.onload = () => addImage(String(reader.result), file.name || "Pasted image");
    reader.readAsDataURL(file);
  }

  function loadVideoFile(file) {
    if (!file.type.startsWith("video/")) return;
    const reader = new FileReader();
    reader.onload = () => addVideo(String(reader.result), file.name || "Video reference", {
      mimeType: file.type,
    });
    reader.onerror = () => setStatus(`Could not read ${file.name || "video"}`);
    reader.readAsDataURL(file);
  }

  function addImage(src, name, options = {}) {
    const img = new Image();
    img.onload = () => {
      const before = options.benchmark ? null : captureSnapshot();
      const maxDimension = options.benchmark ? 320 : 620;
      const ratio = Math.min(1, maxDimension / Math.max(img.naturalWidth, img.naturalHeight));
      const width = Math.max(120, Math.round(img.naturalWidth * ratio));
      const height = Math.max(90, Math.round(img.naturalHeight * ratio));
      const workspaceRect = els.workspace.getBoundingClientRect();
      const center = screenToWorld(
        workspaceRect.left + workspaceRect.width / 2,
        workspaceRect.top + workspaceRect.height / 2,
      );
      const index = state.assets.length;
      const offset = index * 22;
      const asset = {
        id: uid("asset"),
        type: "image",
        referenceNumber: nextReferenceNumber(),
        name,
        src,
        naturalWidth: img.naturalWidth,
        naturalHeight: img.naturalHeight,
        x: options.benchmark ? (index % 10) * 370 : center.x - width / 2 + offset,
        y: options.benchmark ? Math.floor(index / 10) * 270 : center.y - height / 2 + offset,
        width,
        height,
        sourceVideoId: options.sourceVideoId || null,
        sourceTimestampMs: Number.isFinite(options.sourceTimestampMs) ? options.sourceTimestampMs : null,
        annotations: [],
      };
      if (options.benchmark) {
        asset.annotations = [
          makeStoredAnnotation({ x: 0.12, y: 0.32, width: 0.76, height: 0.55 }, "jacket without logo", 0),
          makeStoredAnnotation({ x: 0.4, y: 0.08, width: 0.2, height: 0.28 }, "face and hair, ignore background", 1),
        ];
      }
      state.assets.push(asset);
      renderAsset(asset);
      asset.annotations.forEach((annotation) => renderAnnotation(asset, annotation));
      if (!options.benchmark) selectItem({ type: "asset", assetId: asset.id });
      updateEmptyState();
      if (options.benchmark) {
        const expected = window.__AI_CANVAS_BENCHMARK__?.expected || 0;
        if (state.assets.length === expected) {
          window.__AI_CANVAS_BENCHMARK__.readyAt = performance.now();
          window.__AI_CANVAS_BENCHMARK__.durationMs =
            window.__AI_CANVAS_BENCHMARK__.readyAt - window.__AI_CANVAS_BENCHMARK__.startedAt;
          setStatus(
            `${state.assets.length} images · ${state.assets.length * 2} annotations · ${Math.round(window.__AI_CANVAS_BENCHMARK__.durationMs)} ms`,
          );
          fitAll();
        }
      } else {
        pushHistory(before);
        setStatus("Image pasted · press R to annotate");
      }
    };
    img.src = src;
  }

  function addVideo(src, name, options = {}) {
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    video.playsInline = true;
    video.onloadedmetadata = () => {
      const before = captureSnapshot();
      const naturalWidth = video.videoWidth || 1280;
      const naturalHeight = video.videoHeight || 720;
      const ratio = Math.min(1, 620 / Math.max(naturalWidth, naturalHeight));
      const width = Math.max(180, Math.round(naturalWidth * ratio));
      const height = Math.max(110, Math.round(naturalHeight * ratio));
      const workspaceRect = els.workspace.getBoundingClientRect();
      const center = screenToWorld(
        workspaceRect.left + workspaceRect.width / 2,
        workspaceRect.top + workspaceRect.height / 2,
      );
      const index = state.assets.length;
      const asset = {
        id: uid("asset"),
        type: "video",
        referenceNumber: nextReferenceNumber(),
        name,
        src,
        sourceFile: options.sourceFile || null,
        sourceUrl: options.sourceUrl || null,
        sourceTitle: options.sourceTitle || name,
        sourceExtractor: options.sourceExtractor || null,
        retrievedAt: options.retrievedAt || null,
        mimeType: options.mimeType || "video/mp4",
        duration: Number.isFinite(video.duration) ? video.duration : 0,
        naturalWidth,
        naturalHeight,
        x: center.x - width / 2 + index * 22,
        y: center.y - height / 2 + index * 22,
        width,
        height,
        videoInstruction: "",
        videoDescription: "",
        videoUse: "",
        videoAvoid: "",
        videoObservations: [],
        annotations: [],
      };
      state.assets.push(asset);
      renderAsset(asset);
      selectItem({ type: "asset", assetId: asset.id });
      updateEmptyState();
      pushHistory(before);
      setStatus("Video added · press R to describe how to use the whole clip");
    };
    video.onerror = () => setStatus(`Could not load video: ${name}`);
    video.src = src;
  }

  function makeStoredAnnotation(region, rawInstruction, index) {
    const parsed = parseInstruction(rawInstruction);
    return {
      id: uid("annotation"),
      letter: annotationLetter(index),
      ...region,
      rawInstruction,
      ...parsed,
    };
  }

  function renderAsset(asset) {
    let element = els.scene.querySelector(`[data-asset-id="${asset.id}"]`);
    if (!element) {
      element = document.createElement("div");
      element.className = "asset";
      element.dataset.assetId = asset.id;
      element.innerHTML = `<span class="asset-label"></span>`;
      els.scene.append(element);
    }
    const isVideo = asset.type === "video";
    let media = element.querySelector("img, video");
    if (!media || (isVideo && media.tagName !== "VIDEO") || (!isVideo && media.tagName !== "IMG")) {
      media?.remove();
      media = document.createElement(isVideo ? "video" : "img");
      media.setAttribute("draggable", "false");
      if (isVideo) {
        media.muted = true;
        media.loop = true;
        media.playsInline = true;
        media.preload = "metadata";
      }
      element.insertBefore(media, element.firstChild);
    }
    element.style.left = `${asset.x}px`;
    element.style.top = `${asset.y}px`;
    element.style.width = `${asset.width}px`;
    element.style.height = `${asset.height}px`;
    if (media.getAttribute("src") !== asset.src) media.src = asset.src;
    if (!isVideo) media.alt = asset.name;
    element.querySelector(".asset-label").textContent = asset.name;
    element.classList.toggle("media-error", Boolean(asset.mediaError));
    if (asset.mediaError) element.dataset.mediaError = asset.mediaError;
    else delete element.dataset.mediaError;
    element.classList.toggle(
      "selected",
      state.selected?.type === "asset" && state.selected.assetId === asset.id,
    );
    element.classList.toggle("multi-selected", state.selectedAssetIds.includes(asset.id));
    syncTransformHandles(
      element,
      state.selected?.type === "asset" && state.selected.assetId === asset.id
        ? ["nw", "ne", "se", "sw"]
        : [],
    );
  }

  function syncTransformHandles(element, handles) {
    [...element.children]
      .filter((child) => child.classList.contains("transform-handle"))
      .forEach((child) => child.remove());
    handles.forEach((handle) => {
      const control = document.createElement("span");
      control.className = "transform-handle";
      control.dataset.handle = handle;
      control.setAttribute("aria-hidden", "true");
      element.append(control);
    });
  }

  function renderAnnotation(asset, annotation) {
    const assetElement = els.scene.querySelector(`[data-asset-id="${asset.id}"]`);
    let element = assetElement.querySelector(`[data-annotation-id="${annotation.id}"]`);
    if (!element) {
      element = document.createElement("div");
      element.className = "annotation";
      element.dataset.annotationId = annotation.id;
      assetElement.append(element);
    }
    element.style.left = `${annotation.x * 100}%`;
    element.style.top = `${annotation.y * 100}%`;
    element.style.width = `${annotation.width * 100}%`;
    element.style.height = `${annotation.height * 100}%`;
    element.classList.toggle("drafting", !annotation.rawInstruction);
    element.classList.toggle(
      "selected",
      state.selected?.type === "annotation" && state.selected.annotationId === annotation.id,
    );
    element.classList.toggle("multi-selected", state.selectedAnnotationIds.includes(annotation.id));
    element.querySelector(".annotation-badge")?.remove();
    if (annotation.rawInstruction) {
      const badge = document.createElement("span");
      badge.className = "annotation-badge";
      badge.textContent = `${annotation.letter} · ${annotation.label}`;
      element.append(badge);
    }
    syncTransformHandles(
      element,
      state.selected?.type === "annotation" && state.selected.annotationId === annotation.id
        ? ["nw", "n", "ne", "e", "se", "s", "sw", "w"]
        : [],
    );
    return element;
  }

  function renderAll() {
    els.scene.innerHTML = "";
    state.selectedAssetIds = state.selectedAssetIds.filter((assetId) => Boolean(findAsset(assetId)));
    state.selectedAnnotationIds = state.selectedAnnotationIds.filter((annotationId) => Boolean(findAnnotation(annotationId)));
    if (state.selected?.type === "assets") {
      state.selected.assetIds = [...state.selectedAssetIds];
      if (!state.selected.assetIds.length) state.selected = null;
    }
    if (state.selected?.type === "annotations") {
      state.selected.annotationIds = [...state.selectedAnnotationIds];
      if (!state.selected.annotationIds.length) state.selected = null;
    }
    state.assets.forEach((asset) => {
      renderAsset(asset);
      asset.annotations.forEach((annotation) => renderAnnotation(asset, annotation));
    });
    if (state.selected?.type === "asset" && !findAsset(state.selected.assetId)) state.selected = null;
    if (state.selected?.type === "annotation" && !findAnnotation(state.selected.annotationId)) state.selected = null;
    renderTransform();
    updateEmptyState();
    renderSelectionPanel();
    renderReferenceList();
  }

  function findAsset(assetId) {
    return state.assets.find((asset) => asset.id === assetId);
  }

  function findAnnotation(annotationId) {
    for (const asset of state.assets) {
      const annotation = asset.annotations.find((item) => item.id === annotationId);
      if (annotation) return { asset, annotation };
    }
    return null;
  }

  function selectItem(selection) {
    state.selected = selection;
    state.selectedAssetIds = selection?.type === "assets"
      ? [...selection.assetIds]
      : selection?.type === "asset"
        ? [selection.assetId]
        : [];
    state.selectedAnnotationIds = selection?.type === "annotations"
      ? [...selection.annotationIds]
      : selection?.type === "annotation"
        ? [selection.annotationId]
        : [];
    state.assets.forEach((asset) => {
      renderAsset(asset);
      asset.annotations.forEach((annotation) => renderAnnotation(asset, annotation));
    });
    renderSelectionPanel();
  }

  function getSelectedAssets() {
    return state.selectedAssetIds.map(findAsset).filter(Boolean);
  }

  function getSelectedAnnotations() {
    return state.selectedAnnotationIds.map(findAnnotation).filter(Boolean);
  }

  function createAnnotation(asset, start, current) {
    const left = clamp(Math.min(start.x, current.x), asset.x, asset.x + asset.width);
    const top = clamp(Math.min(start.y, current.y), asset.y, asset.y + asset.height);
    const right = clamp(Math.max(start.x, current.x), asset.x, asset.x + asset.width);
    const bottom = clamp(Math.max(start.y, current.y), asset.y, asset.y + asset.height);
    return {
      id: uid("annotation"),
      letter: annotationLetter(asset.annotations.length),
      x: (left - asset.x) / asset.width,
      y: (top - asset.y) / asset.height,
      width: (right - left) / asset.width,
      height: (bottom - top) / asset.height,
      rawInstruction: "",
      label: "Reference",
      description: "",
      use: "",
      avoid: "",
    };
  }

  function openAnnotationInput(asset, annotation, options = {}) {
    const element = renderAnnotation(asset, annotation);
    element.querySelector(".annotation-input-wrap")?.remove();
    const before = options.before || captureSnapshot();
    const wasExisting = Boolean(options.editing);
    const wrapper = document.createElement("div");
    wrapper.className = "annotation-input-wrap";
    const input = document.createElement("input");
    input.placeholder = "e.g. jacket without logo";
    input.setAttribute("aria-label", "Describe how to use this region");
    input.value = wasExisting ? annotation.rawInstruction : "";
    wrapper.append(input);
    element.append(wrapper);

    const commit = () => {
      const raw = input.value.trim();
      if (!raw) {
        if (wasExisting) {
          wrapper.remove();
          renderAnnotation(asset, annotation);
          setStatus("Instruction edit cancelled");
          return;
        }
        asset.annotations = asset.annotations.filter((item) => item.id !== annotation.id);
        element.remove();
        renderReferenceList();
        selectItem({ type: "asset", assetId: asset.id });
        setStatus("Empty region discarded");
        return;
      }
      Object.assign(annotation, { rawInstruction: raw, ...parseInstruction(raw) });
      wrapper.remove();
      renderAnnotation(asset, annotation);
      selectItem({ type: "annotation", assetId: asset.id, annotationId: annotation.id });
      renderReferenceList();
      pushHistory(before);
      setStatus(`${annotation.label} saved · draw another region`);
    };

    input.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Enter") {
        event.preventDefault();
        commit();
      } else if (event.key === "Escape") {
        event.preventDefault();
        if (wasExisting) {
          wrapper.remove();
          renderAnnotation(asset, annotation);
          setStatus("Instruction edit cancelled");
          setTool("select");
          return;
        }
        input.value = "";
        commit();
        setTool("select");
      }
    });

    requestAnimationFrame(() => input.focus({ preventScroll: true }));
  }

  function openVideoInstructionInput(asset, options = {}) {
    const element = renderAsset(asset) || els.scene.querySelector(`[data-asset-id="${asset.id}"]`);
    element.querySelector(".annotation-input-wrap")?.remove();
    const before = options.before || captureSnapshot();
    const wrapper = document.createElement("div");
    wrapper.className = "annotation-input-wrap";
    const input = document.createElement("input");
    input.placeholder = "e.g. use the camera movement and pacing";
    input.setAttribute("aria-label", "Describe how to use this entire video");
    input.value = asset.videoInstruction || "";
    wrapper.append(input);
    element.append(wrapper);
    const cancel = () => {
      wrapper.remove();
      setStatus("Video instruction edit cancelled");
    };
    const commit = () => {
      const raw = input.value.trim();
      if (!raw) {
        cancel();
        return;
      }
      const parsed = parseInstruction(raw);
      asset.videoInstruction = raw;
      asset.videoDescription = parsed.description;
      asset.videoUse = parsed.use;
      asset.videoAvoid = parsed.avoid;
      wrapper.remove();
      selectItem({ type: "asset", assetId: asset.id });
      renderReferenceList();
      pushHistory(before);
      setStatus(`${parsed.label} saved for the whole video · select another video or press Esc`);
    };
    input.addEventListener("keydown", (event) => {
      event.stopPropagation();
      if (event.key === "Enter") {
        event.preventDefault();
        commit();
      } else if (event.key === "Escape") {
        event.preventDefault();
        cancel();
        setTool("select");
      }
    });
    requestAnimationFrame(() => input.focus({ preventScroll: true }));
  }

  function waitForMediaEvent(media, eventName, timeoutMs = 15000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup();
        reject(new Error(`Timed out while reading video ${eventName}.`));
      }, timeoutMs);
      const cleanup = () => {
        clearTimeout(timer);
        media.removeEventListener(eventName, success);
        media.removeEventListener("error", failure);
      };
      const success = () => { cleanup(); resolve(); };
      const failure = () => { cleanup(); reject(new Error("The video could not be decoded.")); };
      media.addEventListener(eventName, success, { once: true });
      media.addEventListener("error", failure, { once: true });
    });
  }

  async function loadVideoForFrames(asset) {
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    video.src = asset.src;
    if (video.readyState < 1) await waitForMediaEvent(video, "loadedmetadata");
    return video;
  }

  async function seekVideo(video, time) {
    const duration = Number.isFinite(video.duration) ? video.duration : 0;
    const target = clamp(Number(time) || 0, 0, Math.max(0, duration - 0.04));
    if (Math.abs(video.currentTime - target) > 0.015) {
      video.currentTime = target;
      await waitForMediaEvent(video, "seeked");
    } else if (video.readyState < 2) {
      await waitForMediaEvent(video, "loadeddata");
    }
  }

  function drawVideoIntoCanvas(video, maxDimension = 1280) {
    const ratio = Math.min(1, maxDimension / Math.max(video.videoWidth || 1, video.videoHeight || 1));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round((video.videoWidth || 1) * ratio));
    canvas.height = Math.max(1, Math.round((video.videoHeight || 1) * ratio));
    canvas.getContext("2d", { alpha: false }).drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas;
  }

  async function captureVideoFrame(asset, time) {
    const video = await loadVideoForFrames(asset);
    try {
      await seekVideo(video, time);
      return drawVideoIntoCanvas(video).toDataURL("image/jpeg", 0.92);
    } finally {
      video.removeAttribute("src");
      video.load();
    }
  }

  async function buildVideoContactSheet(asset, frameCount = 4) {
    const video = await loadVideoForFrames(asset);
    const columns = 2;
    const rows = Math.ceil(frameCount / columns);
    const cellWidth = 320;
    const cellHeight = 180;
    const canvas = document.createElement("canvas");
    canvas.width = columns * cellWidth;
    canvas.height = rows * cellHeight;
    const context = canvas.getContext("2d", { alpha: false });
    context.fillStyle = "#111318";
    context.fillRect(0, 0, canvas.width, canvas.height);
    try {
      for (let index = 0; index < frameCount; index += 1) {
        const time = video.duration > 0 ? (video.duration * (index + 0.5)) / frameCount : 0;
        await seekVideo(video, time);
        const sourceRatio = (video.videoWidth || 1) / (video.videoHeight || 1);
        const cellRatio = cellWidth / cellHeight;
        let width = cellWidth;
        let height = cellHeight;
        if (sourceRatio > cellRatio) height = cellWidth / sourceRatio;
        else width = cellHeight * sourceRatio;
        const left = (index % columns) * cellWidth + (cellWidth - width) / 2;
        const top = Math.floor(index / columns) * cellHeight + (cellHeight - height) / 2;
        context.drawImage(video, left, top, width, height);
      }
      return canvas.toDataURL("image/jpeg", 0.88);
    } finally {
      video.removeAttribute("src");
      video.load();
    }
  }

  async function extractVideoFrames(asset, count, currentTime = null) {
    const times = currentTime == null
      ? Array.from({ length: count }, (_, index) => asset.duration > 0 ? (asset.duration * (index + 0.5)) / count : 0)
      : [currentTime];
    setStatus(`Extracting ${times.length} frame${times.length === 1 ? "" : "s"} from ${asset.name}â€¦`);
    try {
      for (let index = 0; index < times.length; index += 1) {
        const time = times[index];
        const dataUrl = await captureVideoFrame(asset, time);
        const baseName = asset.name.replace(/\.[^.]+$/, "") || "Video";
        addImage(dataUrl, `${baseName} · ${formatDuration(time)}.jpg`, {
          sourceVideoId: asset.id,
          sourceTimestampMs: Math.round(time * 1000),
        });
      }
      setStatus(`${times.length} frame${times.length === 1 ? "" : "s"} extracted as image references`);
    } catch (error) {
      console.error(error);
      setStatus(error.message || "Frame extraction failed");
    }
  }

  function cropAnnotation(asset, annotation) {
    const source = new Image();
    return new Promise((resolve, reject) => {
      source.onload = () => {
        const sx = Math.round(annotation.x * source.naturalWidth);
        const sy = Math.round(annotation.y * source.naturalHeight);
        const sw = Math.max(1, Math.round(annotation.width * source.naturalWidth));
        const sh = Math.max(1, Math.round(annotation.height * source.naturalHeight));
        const max = 512;
        const ratio = Math.min(1, max / Math.max(sw, sh));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(sw * ratio));
        canvas.height = Math.max(1, Math.round(sh * ratio));
        const context = canvas.getContext("2d", { alpha: false });
        context.drawImage(source, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/png"));
      };
      source.onerror = () => reject(new Error(asset.mediaError || `Could not read image source: ${asset.name}`));
      source.src = asset.src;
    });
  }

  function getCompiledReferences() {
    const references = [];
    state.assets.forEach((asset, assetIndex) => {
      asset.annotations.forEach((annotation) => {
        if (!annotation.rawInstruction) return;
        const assetNumber = String(asset.referenceNumber || assetIndex + 1).padStart(2, "0");
        references.push({
          asset,
          annotation,
          filename: `R${assetNumber}${annotation.letter}.png`,
        });
      });
    });
    return references;
  }

  function videoExtension(asset) {
    const byMime = {
      "video/mp4": "mp4",
      "video/webm": "webm",
      "video/quicktime": "mov",
      "video/x-matroska": "mkv",
    };
    if (byMime[asset.mimeType]) return byMime[asset.mimeType];
    const match = String(asset.name || asset.sourceFile || "").match(/\.([a-z0-9]{2,5})(?:$|\?)/i);
    return match?.[1]?.toLowerCase() || "mp4";
  }

  function getCompiledVideoReferences() {
    return state.assets
      .filter((asset) => asset.type === "video" && asset.videoInstruction?.trim())
      .map((asset, assetIndex) => ({
        kind: "video",
        asset,
        annotation: null,
        filename: `V${String(asset.referenceNumber || assetIndex + 1).padStart(2, "0")}.${videoExtension(asset)}`,
        instruction: asset.videoInstruction.trim(),
      }));
  }

  function getAllCompiledReferences() {
    return [
      ...getCompiledReferences().map((reference) => ({ ...reference, kind: "image", instruction: reference.annotation.rawInstruction })),
      ...getCompiledVideoReferences(),
    ];
  }

  async function renderReferenceList() {
    const references = getAllCompiledReferences();
    els.cropCount.textContent = String(references.length);
    els.referenceList.innerHTML = "";
    if (!references.length) {
      els.referenceList.innerHTML = `<p class="muted">Annotations will appear here.</p>`;
      return;
    }
    for (const reference of references) {
      const card = document.createElement("article");
      card.className = "reference-card";
      if (reference.kind === "video") {
        card.innerHTML = `
          <div class="reference-video-thumb" aria-hidden="true">â–¶</div>
          <div class="reference-copy">
            <strong>${escapeHtml(parseInstruction(reference.instruction).label)}</strong>
            <span>Whole video · ${formatDuration(reference.asset.duration)}</span>
            <small>${reference.filename}</small>
          </div>
        `;
      } else {
        const crop = await cropAnnotation(reference.asset, reference.annotation);
        card.innerHTML = `
          <img src="${crop}" alt="${escapeAttribute(reference.annotation.label)}" />
          <div class="reference-copy">
            <strong>${escapeHtml(reference.annotation.label)}</strong>
            <small>${reference.filename}</small>
          </div>
        `;
      }
      card.addEventListener("click", () => {
        selectItem(reference.kind === "video"
          ? { type: "asset", assetId: reference.asset.id }
          : { type: "annotation", assetId: reference.asset.id, annotationId: reference.annotation.id });
        setActivePanelTab("selection");
      });
      els.referenceList.append(card);
    }
  }

  function renderSelectionPanel() {
    const selected = state.selected;
    els.selectionDetails.innerHTML = "";
    els.selectionEmpty.hidden = Boolean(selected);
    els.selectionDetails.hidden = !selected;
    if (!selected) return;

    if (selected.type === "assets") {
      els.selectionDetails.innerHTML = `
        <h2 class="selection-title">${selected.assetIds.length} images selected</h2>
        <p class="muted">Drag any selected image to move the group. Use Delete to remove them.</p>
      `;
      return;
    }

    if (selected.type === "annotations") {
      els.selectionDetails.innerHTML = `
        <h2 class="selection-title">${selected.annotationIds.length} regions selected</h2>
        <p class="muted">Drag any selected region to move the group. Use Delete or Ctrl+D on the full selection.</p>
      `;
      return;
    }

    if (selected.type === "asset") {
      const asset = findAsset(selected.assetId);
      if (!asset) return;
      if (asset.type === "video") {
        els.selectionDetails.innerHTML = `
          <h2 class="selection-title">Video</h2>
          <video class="selection-video-preview" controls muted playsinline preload="metadata"></video>
          <div class="selection-field"><label>Name</label><input data-field="asset-name" value="${escapeAttribute(asset.name)}" /></div>
          <div class="selection-field"><label>Whole-video instruction</label><textarea data-field="video-instruction" rows="3" placeholder="Use its camera movement and pacing">${escapeHtml(asset.videoInstruction || "")}</textarea></div>
          <p class="muted">${formatDuration(asset.duration)} · ${asset.naturalWidth}×${asset.naturalHeight} · the full video is the reference.</p>
          <div class="video-actions">
            <button class="button secondary" data-action="capture-frame" type="button">Capture current frame</button>
            <button class="button secondary" data-action="annotate-video" type="button">Edit instruction</button>
          </div>
          <div class="selection-field">
            <label>Even frame extraction</label>
            <select data-field="frame-count">
              <option value="4">4 frames</option>
              <option value="8" selected>8 frames</option>
              <option value="12">12 frames</option>
            </select>
          </div>
          <button class="button primary" data-action="extract-frames" type="button">Extract evenly across video</button>
          ${asset.mediaError ? `<p class="selection-media-error">${escapeHtml(asset.mediaError)}</p>` : ""}
        `;
        const preview = els.selectionDetails.querySelector(".selection-video-preview");
        preview.src = asset.src;
        const nameInput = els.selectionDetails.querySelector('[data-field="asset-name"]');
        const instructionInput = els.selectionDetails.querySelector('[data-field="video-instruction"]');
        let beforeName = null;
        let beforeInstruction = null;
        nameInput.addEventListener("focus", () => { beforeName = captureSnapshot(); });
        nameInput.addEventListener("input", () => { asset.name = nameInput.value; renderAsset(asset); });
        nameInput.addEventListener("change", () => pushHistory(beforeName));
        instructionInput.addEventListener("focus", () => { beforeInstruction = captureSnapshot(); });
        instructionInput.addEventListener("input", () => {
          asset.videoInstruction = instructionInput.value;
          renderReferenceList();
          invalidateAIDraft("A whole-video instruction changed. Regenerate before exporting.");
          scheduleSave();
        });
        instructionInput.addEventListener("change", () => {
          const parsed = parseInstruction(instructionInput.value);
          asset.videoDescription = parsed.description;
          asset.videoUse = parsed.use;
          asset.videoAvoid = parsed.avoid;
          pushHistory(beforeInstruction);
          renderReferenceList();
        });
        els.selectionDetails.querySelector('[data-action="capture-frame"]').addEventListener("click", () => {
          extractVideoFrames(asset, 1, preview.currentTime || 0);
        });
        els.selectionDetails.querySelector('[data-action="annotate-video"]').addEventListener("click", () => {
          openVideoInstructionInput(asset, { before: captureSnapshot() });
        });
        els.selectionDetails.querySelector('[data-action="extract-frames"]').addEventListener("click", () => {
          const count = Number(els.selectionDetails.querySelector('[data-field="frame-count"]').value) || 8;
          extractVideoFrames(asset, count);
        });
        return;
      }
      els.selectionDetails.innerHTML = `
        <h2 class="selection-title">Image</h2>
        <div class="selection-field"><label>Name</label><input data-field="asset-name" value="${escapeAttribute(asset.name)}" /></div>
        ${asset.mediaError ? `<p class="selection-media-error">${escapeHtml(asset.mediaError)}</p>` : ""}
        <p class="muted">${asset.annotations.length} annotation${asset.annotations.length === 1 ? "" : "s"}</p>
      `;
      const input = els.selectionDetails.querySelector('[data-field="asset-name"]');
      let beforeEdit = null;
      input.addEventListener("focus", () => { beforeEdit = captureSnapshot(); });
      input.addEventListener("input", () => {
        asset.name = input.value;
        renderAsset(asset);
      });
      input.addEventListener("change", () => pushHistory(beforeEdit));
      return;
    }

    const result = findAnnotation(selected.annotationId);
    if (!result) return;
    const { asset, annotation } = result;
    els.selectionDetails.innerHTML = `
      <h2 class="selection-title">${annotation.letter} · ${escapeHtml(annotation.label)}</h2>
      <div class="selection-field"><label>Raw instruction</label><input data-field="raw" value="${escapeAttribute(annotation.rawInstruction)}" /></div>
      <div class="selection-field"><label>Label</label><input data-field="label" value="${escapeAttribute(annotation.label)}" /></div>
    `;
    els.selectionDetails.querySelectorAll("[data-field]").forEach((input) => {
      let beforeEdit = null;
      input.addEventListener("focus", () => { beforeEdit = captureSnapshot(); });
      input.addEventListener("input", () => {
        const field = input.dataset.field;
        if (field === "raw") {
          annotation.rawInstruction = input.value;
        } else {
          annotation[field] = input.value;
        }
        renderAnnotation(asset, annotation);
        renderReferenceList();
      });
      input.addEventListener("change", () => {
        if (input.dataset.field === "raw" && input.value.trim()) {
          Object.assign(annotation, parseInstruction(input.value));
          renderAnnotation(asset, annotation);
          renderSelectionPanel();
          renderReferenceList();
        }
        pushHistory(beforeEdit);
      });
    });
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function escapeAttribute(value) {
    return escapeHtml(value);
  }

  function buildPromptText() {
    const references = getCompiledReferences();
    const videoReferences = getCompiledVideoReferences();
    const objective = els.objectiveInput.value.trim() || "[Describe what you want to create]";
    const format = els.formatInput.value.trim();
    const lines = ["OBJECTIVE", objective, ""];

    const groups = new Map([["Reference crops", references]]);

    let referenceNumber = 0;
    groups.forEach((groupReferences, groupName) => {
      lines.push(groupName.toUpperCase());
      groupReferences.forEach((reference) => {
        referenceNumber += 1;
        const { annotation, filename } = reference;
        lines.push(`${referenceNumber}. ${filename}`);
        lines.push(`   Instruction: ${annotation.rawInstruction}`);
        lines.push("");
      });
    });

    if (videoReferences.length) {
      lines.push("VIDEO REFERENCES");
      videoReferences.forEach((reference) => {
        referenceNumber += 1;
        lines.push(`${referenceNumber}. ${reference.filename}`);
        lines.push(`   Whole-video instruction: ${reference.instruction}`);
        lines.push("");
      });
    }

    if (format) {
      lines.push("PROMPT DRAFTING INSTRUCTIONS", format, "");
    }
    lines.push(
      "REFERENCE RULE",
      "Use each crop or video only for the purpose described beside its exact filename. Do not assume access to original source images beyond these exported references.",
    );

    return lines.join("\n");
  }

  function compilePrompt() {
    const references = getAllCompiledReferences();
    const before = captureSnapshot();
    const finalPrompt = buildPromptText();
    state.aiDraft = {
      source: "rule-based",
      model: "deterministic-local",
      summary: "Local rule-based draft; crops were not transmitted or visually analyzed.",
      finalPrompt,
      originalPrompt: finalPrompt,
      edited: false,
      stale: false,
      fingerprint: draftFingerprint(),
      generatedAt: new Date().toISOString(),
      responseId: null,
      usage: null,
    };
    state.lastDraftError = "";
    renderPromptState();
    setActivePanelTab("prompt");
    if (els.shell.classList.contains("panel-collapsed")) togglePanel(false);
    pushHistory(before, { preserveDraft: true });
    setStatus(`${references.length} crop${references.length === 1 ? "" : "s"} compiled`);
  }

  function selectedProvider() {
    return state.providers.find((provider) => provider.id === els.providerInput.value) || null;
  }

  function setProviderConnection(kind, title, message) {
    els.providerConnection.className = `provider-connection ${kind}`;
    els.providerConnectionTitle.textContent = title;
    els.keyHint.textContent = message;
  }

  function localServerError(error, action) {
    if (error instanceof TypeError && /fetch|network/i.test(error.message || "")) {
      return `AI Canvas could not reach its local app server while ${action}. Restart the AI Canvas server, then refresh this page.`;
    }
    return error.message || `The local app server could not finish ${action}.`;
  }

  async function readApiResult(response, action) {
    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error(`LOCAL_SERVER_MISSING: This page is running without the AI Canvas app server. Restart it, refresh the page, and try ${action} again.`);
    }
    return response.json().catch(() => ({}));
  }

  function renderProviderOptions() {
    const preferred = state.providerId || els.providerInput.value || "openai";
    els.providerInput.innerHTML = "";
    state.providers.forEach((provider) => {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = provider.name;
      els.providerInput.append(option);
    });
    els.providerInput.value = state.providers.some((provider) => provider.id === preferred)
      ? preferred
      : state.providers[0]?.id || "openai";
  }

  function renderProviderSettings() {
    const provider = selectedProvider();
    if (!provider) {
      els.modelInput.innerHTML = "";
      setProviderConnection("error", "Provider unavailable", "Reload AI Canvas and try again.");
      return;
    }
    state.providerId = provider.id;
    const previousModel = state.providerModels[provider.id];
    els.modelInput.innerHTML = "";
    provider.models.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = `${model.name}${model.note ? ` · ${model.note}` : ""}`;
      els.modelInput.append(option);
    });
    const modelIds = provider.models.map((model) => model.id);
    els.modelInput.value = modelIds.includes(previousModel) ? previousModel : provider.defaultModel;
    state.providerModel = els.modelInput.value;
    state.providerModels[provider.id] = els.modelInput.value;
    if (provider.configured) {
      els.providerStatus.textContent = `${provider.name} · connected`;
      setProviderConnection(
        "success",
        state.mockMode ? "Connected in test mode" : "Connected",
        provider.credentialStorage === "settings-file"
          ? `${provider.name} is ready. Its key is saved in local app settings.`
          : `${provider.name} is ready for this session.`,
      );
      els.removeProviderButton.hidden = false;
    } else {
      els.providerStatus.textContent = `${provider.name} · not connected`;
      const article = /^[aeiou]/i.test(provider.name) ? "an" : "a";
      setProviderConnection("neutral", "Not connected", `Paste ${article} ${provider.name} API key, then choose Save & connect.`);
      els.removeProviderButton.hidden = true;
    }
    els.apiKeyInput.placeholder = provider.id === "gemini"
      ? "Paste Gemini API key"
      : "Paste OpenAI API key";
  }

  async function checkProviderHealth() {
    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      if (!response.ok) throw new Error("Local drafting server unavailable");
      const health = await response.json();
      const requestedProvider = els.providerInput.value || state.providerId;
      state.providers = health.providers?.length ? health.providers : cloneProviderRegistry(FALLBACK_PROVIDERS);
      state.mockMode = Boolean(health.mockMode);
      els.projectsFolderPath.textContent = health.projectsFolder || "Project folder unavailable";
      const knownProviderIds = state.providers.map((provider) => provider.id);
      state.providerId = knownProviderIds.includes(requestedProvider) ? requestedProvider : knownProviderIds[0] || "openai";
      renderProviderOptions();
      renderProviderSettings();
      const projectsReady = await refreshProjects();
      return { ...health, projectsReady };
    } catch (error) {
      state.providers = cloneProviderRegistry(FALLBACK_PROVIDERS);
      state.mockMode = false;
      renderProviderOptions();
      renderProviderSettings();
      els.providerStatus.textContent = "AI server not running";
      setProviderConnection("error", "Local server unavailable", localServerError(error, "checking provider settings"));
      els.projectsFolderPath.textContent = "AI Canvas app server not running";
      renderProjectList();
      return null;
    }
  }

  function renderExportPreferences() {
    els.copyPromptOnExportInput.checked = state.exportPreferences.copyPrompt;
    els.openFolderOnExportInput.checked = state.exportPreferences.openFolder;
  }

  async function loadExportPreferences() {
    try {
      const response = await fetch("/api/preferences", { cache: "no-store" });
      if (!response.ok) throw new Error("Could not load export settings");
      const result = await response.json();
      state.exportPreferences = {
        copyPrompt: result.preferences?.copyPromptOnExport !== false,
        openFolder: result.preferences?.openFolderOnExport !== false,
      };
      state.workspacePreferences = {
        lastActiveProjectId: result.preferences?.lastActiveProjectId || null,
        openProjectIds: Array.isArray(result.preferences?.openProjectIds) ? result.preferences.openProjectIds : [],
      };
      renderExportPreferences();
    } catch (error) {
      console.error(error);
      renderExportPreferences();
    }
  }

  async function saveExportPreferences() {
    state.exportPreferences = {
      copyPrompt: els.copyPromptOnExportInput.checked,
      openFolder: els.openFolderOnExportInput.checked,
    };
    try {
      const response = await fetch("/api/preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          copyPromptOnExport: state.exportPreferences.copyPrompt,
          openFolderOnExport: state.exportPreferences.openFolder,
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "Could not save export settings");
      setStatus("Export settings saved");
    } catch (error) {
      console.error(error);
      setStatus("Export settings could not be saved");
    }
  }

  function scheduleWorkspacePreferences() {
    clearTimeout(state.preferencesSaveTimer);
    state.preferencesSaveTimer = setTimeout(async () => {
      const openProjectIds = state.projects
        .filter((project) => !state.closedProjectIds.has(project.id))
        .map((project) => project.id);
      state.workspacePreferences = {
        lastActiveProjectId: state.currentProject?.id || null,
        openProjectIds,
      };
      try {
        await fetch("/api/preferences", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state.workspacePreferences),
        });
      } catch (error) {
        console.error(error);
      }
    }, 180);
  }

  async function saveProviderCredential() {
    const providerId = els.providerInput.value;
    const apiKey = els.apiKeyInput.value.trim();
    if (!apiKey) {
      setStatus("Paste an API key first");
      setProviderConnection("error", "API key required", "Paste the selected provider's API key before connecting.");
      els.apiKeyInput.focus();
      return false;
    }
    els.saveProviderButton.disabled = true;
    els.saveProviderButton.textContent = "Connecting…";
    setProviderConnection("connecting", "Checking key…", `Connecting to ${selectedProvider()?.name || "provider"}.`);
    try {
      const response = await fetch(`/api/providers/${encodeURIComponent(providerId)}/credential`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apiKey }),
      });
      const result = await readApiResult(response, "connecting the provider");
      if (!response.ok) throw new Error(result.error || "Provider setup failed");
      els.apiKeyInput.value = "";
      await checkProviderHealth();
      setStatus(`${selectedProvider()?.name || "Provider"} connected`);
      return true;
    } catch (error) {
      const isLocalFailure = (error instanceof TypeError && /fetch|network/i.test(error.message || ""))
        || String(error.message || "").startsWith("LOCAL_SERVER_MISSING:");
      const message = isLocalFailure && String(error.message || "").startsWith("LOCAL_SERVER_MISSING:")
        ? String(error.message).replace("LOCAL_SERVER_MISSING: ", "")
        : localServerError(error, "connecting the provider");
      setProviderConnection("error", isLocalFailure ? "Local server unavailable" : "Could not connect", message);
      setStatus(message);
      return false;
    } finally {
      els.saveProviderButton.disabled = false;
      els.saveProviderButton.textContent = "Save & connect";
    }
  }

  async function removeProviderCredential() {
    const provider = selectedProvider();
    if (!provider) return;
    try {
      setProviderConnection("connecting", "Removing key…", `Disconnecting ${provider.name}.`);
      const response = await fetch(`/api/providers/${encodeURIComponent(provider.id)}/credential`, { method: "DELETE" });
      const result = await readApiResult(response, "removing the provider key");
      if (!response.ok) throw new Error(result.error || "Could not remove provider key");
      await checkProviderHealth();
      setStatus(`${provider.name} key removed`);
    } catch (error) {
      const isLocalFailure = (error instanceof TypeError && /fetch|network/i.test(error.message || ""))
        || String(error.message || "").startsWith("LOCAL_SERVER_MISSING:");
      const message = isLocalFailure && String(error.message || "").startsWith("LOCAL_SERVER_MISSING:")
        ? String(error.message).replace("LOCAL_SERVER_MISSING: ", "")
        : localServerError(error, "removing the provider key");
      setProviderConnection("error", isLocalFailure ? "Local server unavailable" : "Could not remove key", message);
      setStatus(message);
    }
  }

  function setCurrentProject(project) {
    state.currentProject = project;
    els.currentProjectName.textContent = project?.name || "No project loaded";
    els.saveProjectButton.disabled = !project;
    renderProjectList();
    renderProjectTabs();
  }

  function renderProjectTabs() {
    els.projectTabs.innerHTML = "";
    state.projects
      .filter((project) => !state.closedProjectIds.has(project.id))
      .forEach((project) => {
        const tab = document.createElement("div");
        tab.className = "project-tab";
        tab.classList.toggle("current", project.id === state.currentProject?.id);
        if (state.renamingProjectId === project.id) {
          const input = document.createElement("input");
          input.className = "project-tab-rename";
          input.value = project.name;
          input.setAttribute("aria-label", "Rename project");
          const finish = async () => {
            if (state.renamingProjectId !== project.id) return;
            await renameCurrentProject(input.value, project.id);
          };
          input.addEventListener("keydown", (event) => {
            if (event.key === "Enter") finish();
            if (event.key === "Escape") {
              state.renamingProjectId = null;
              renderProjectTabs();
            }
          });
          input.addEventListener("blur", finish);
          tab.append(input);
          requestAnimationFrame(() => {
            input.focus();
            input.select();
          });
        } else {
          const name = document.createElement("button");
          name.type = "button";
          name.className = "project-tab-name";
          name.textContent = project.name;
          name.title = `${project.name} — double-click to rename`;
          name.addEventListener("click", () => loadProject(project.id));
          name.addEventListener("dblclick", async (event) => {
            event.preventDefault();
            if (project.id !== state.currentProject?.id) await loadProject(project.id);
            state.renamingProjectId = project.id;
            renderProjectTabs();
          });
          tab.append(name);
        }
        const close = document.createElement("button");
        close.type = "button";
        close.className = "project-tab-close";
        close.textContent = "×";
        close.title = "Close tab (folder is kept)";
        close.setAttribute("aria-label", `Close ${project.name} tab`);
        close.addEventListener("click", () => closeProjectTab(project.id));
        tab.append(close);
        els.projectTabs.append(tab);
      });
  }

  async function closeProjectTab(projectId) {
    if (projectId === state.currentProject?.id) await saveCurrentProject({ quiet: true, refresh: false });
    state.closedProjectIds.add(projectId);
    if (projectId === state.currentProject?.id) {
      const next = state.projects.find((project) => !state.closedProjectIds.has(project.id));
      if (next) await loadProject(next.id);
      else {
        state.currentProject = null;
        applySnapshot({}, { save: false, preserveProviderSettings: true });
        setCurrentProject(null);
        setStatus("Project tab closed; its folder is still saved");
      }
    }
    renderProjectTabs();
    scheduleWorkspacePreferences();
  }

  function renderProjectList() {
    els.projectList.innerHTML = "";
    if (!state.projects.length) {
      els.projectList.innerHTML = `<p class="muted">No saved projects yet.</p>`;
      return;
    }
    state.projects.forEach((project) => {
      const card = document.createElement("article");
      card.className = "project-card";
      card.classList.toggle("current", project.id === state.currentProject?.id);
      const updated = project.updatedAt ? new Date(project.updatedAt).toLocaleString() : "Not saved";
      card.innerHTML = `
        <div class="project-card-copy">
          <strong>${escapeHtml(project.name)}</strong>
          <small>${project.assetCount || 0} asset${project.assetCount === 1 ? "" : "s"} · ${escapeHtml(updated)}</small>
        </div>
        <div class="project-card-actions">
          <button class="button ghost project-switch-button" type="button">${project.id === state.currentProject?.id ? "Open" : "Switch"}</button>
          <button class="text-button project-duplicate-button" type="button">Duplicate</button>
          <button class="text-button danger project-delete-button" type="button">Delete</button>
        </div>
      `;
      card.querySelector(".project-switch-button").addEventListener("click", () => {
        state.closedProjectIds.delete(project.id);
        loadProject(project.id);
      });
      card.querySelector(".project-duplicate-button").addEventListener("click", () => duplicateProject(project.id));
      card.querySelector(".project-delete-button").addEventListener("click", () => deleteProject(project));
      els.projectList.append(card);
    });
  }

  async function duplicateProject(projectId) {
    try {
      if (state.currentProject?.id === projectId && !(await saveCurrentProject({ quiet: true, refresh: false }))) return;
      setStatus("Duplicating projectâ€¦");
      const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/duplicate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const project = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(project.error || "Project duplication failed");
      state.closedProjectIds.delete(project.id);
      await refreshProjects();
      await loadProject(project.id);
      setStatus(`${project.name} created`);
    } catch (error) {
      setStatus(error.message || "Project duplication failed");
    }
  }

  async function deleteProject(project) {
    const confirmed = window.confirm(
      `Delete “${project.name}” permanently?\n\nIts project folder, source media, and every export package will be removed. This cannot be undone.`,
    );
    if (!confirmed) return;
    try {
      clearTimeout(state.folderSaveTimer);
      const response = await fetch(`/api/projects/${encodeURIComponent(project.id)}`, { method: "DELETE" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "Project deletion failed");
      const wasCurrent = state.currentProject?.id === project.id;
      state.closedProjectIds.delete(project.id);
      if (wasCurrent) {
        state.currentProject = null;
        applySnapshot({}, { save: false, preserveProviderSettings: true });
        setCurrentProject(null);
      }
      await refreshProjects();
      if (wasCurrent) {
        const next = state.projects[0];
        if (next) await loadProject(next.id);
        else await createProject({ quick: true, startup: true });
      }
      scheduleWorkspacePreferences();
      setStatus(`${project.name} and its folder were deleted permanently`);
    } catch (error) {
      setStatus(error.message || "Project deletion failed");
    }
  }

  async function refreshProjects() {
    try {
      const response = await fetch("/api/projects", { cache: "no-store" });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "Could not load projects");
      state.projects = result.projects || [];
      if (!state.workspaceTabsInitialized) {
        const openIds = new Set(state.workspacePreferences.openProjectIds || []);
        state.closedProjectIds = openIds.size
          ? new Set(state.projects.filter((project) => !openIds.has(project.id)).map((project) => project.id))
          : new Set();
        state.workspaceTabsInitialized = true;
      }
      if (result.folder) els.projectsFolderPath.textContent = result.folder;
      renderProjectList();
      renderProjectTabs();
      return true;
    } catch {
      state.projects = [];
      renderProjectList();
      renderProjectTabs();
      return false;
    }
  }

  async function saveCurrentProject({ quiet = false, refresh = true } = {}) {
    if (!state.currentProject) {
      if (!quiet) {
        setStatus("Create or load a project first");
        setActivePanelTab("projects");
      }
      return false;
    }
    const targetProjectId = state.currentProject.id;
    const targetProjectName = state.currentProject.name;
    const snapshot = captureSnapshot();
    els.saveProjectButton.disabled = true;
    els.saveProjectButton.textContent = "Saving…";
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(targetProjectId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ snapshot }),
      });
      const project = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(project.error || "Project save failed");
      if (refresh) await refreshProjects();
      else {
        const index = state.projects.findIndex((item) => item.id === project.id);
        if (index >= 0) state.projects[index] = project;
      }
      if (state.currentProject?.id === targetProjectId) {
        state.currentProject = project;
        setCurrentProject(project);
        els.saveText.textContent = `Saved to ${project.name}`;
      }
      if (!quiet) setStatus(`${project.name} saved`);
      return true;
    } catch (error) {
      setStatus(error.message || `${targetProjectName} save failed`);
      return false;
    } finally {
      els.saveProjectButton.disabled = !state.currentProject;
      els.saveProjectButton.textContent = "Save current project";
    }
  }

  async function createProject({ quick = false, preserveCanvas = false, startup = false } = {}) {
    clearTimeout(state.folderSaveTimer);
    if (state.currentProject && !(await saveCurrentProject({ quiet: true, refresh: false }))) return;
    const preservedSnapshot = preserveCanvas ? captureSnapshot() : null;
    const name = quick ? "Untitled project" : els.newProjectNameInput.value.trim() || "Untitled project";
    els.createProjectButton.disabled = true;
    els.topCreateProjectButton.disabled = true;
    try {
      const response = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const project = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(project.error || "Project creation failed");
      state.history.past = [];
      state.history.future = [];
      state.closedProjectIds.delete(project.id);
      setCurrentProject(project);
      applySnapshot(preservedSnapshot || {}, { save: false, preserveProviderSettings: true });
      els.newProjectNameInput.value = "";
      await saveCurrentProject({ quiet: true });
      scheduleWorkspacePreferences();
      if (quick && !startup) {
        state.renamingProjectId = project.id;
        renderProjectTabs();
      }
      if (startup) setStatus(`${project.name} created and loaded`);
    } catch (error) {
      setStatus(error.message || "Project creation failed");
    } finally {
      els.createProjectButton.disabled = false;
      els.topCreateProjectButton.disabled = false;
    }
  }

  async function renameCurrentProject(value, projectId = state.currentProject?.id) {
    if (!projectId || projectId !== state.currentProject?.id) return false;
    const name = String(value || "").trim();
    if (!name) {
      setStatus("Project name cannot be empty");
      state.renamingProjectId = projectId;
      renderProjectTabs();
      return false;
    }
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const project = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(project.error || "Project rename failed");
      state.currentProject = project;
      state.renamingProjectId = null;
      await refreshProjects();
      setCurrentProject(project);
      setStatus(`Renamed to ${project.name}`);
      return true;
    } catch (error) {
      setStatus(error.message || "Project rename failed");
      return false;
    }
  }

  async function loadProject(projectId) {
    if (projectId === state.currentProject?.id) {
      return;
    }
    clearTimeout(state.folderSaveTimer);
    if (state.currentProject && !(await saveCurrentProject({ quiet: true, refresh: false }))) return;
    setStatus("Loading project…");
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, { cache: "no-store" });
      const project = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(project.error || "Project load failed");
      state.history.past = [];
      state.history.future = [];
      state.closedProjectIds.delete(project.id);
      setCurrentProject(project);
      applySnapshot(project.snapshot || {}, { save: false, preserveProviderSettings: true });
      updateHistoryButtons();
      els.saveText.textContent = `Saved to ${project.name}`;
      setStatus(`${project.name} loaded`);
      const mediaErrors = (project.snapshot?.assets || []).filter((asset) => asset.mediaError);
      if (mediaErrors.length) {
        setStatus(`${project.name} loaded with ${mediaErrors.length} missing media file${mediaErrors.length === 1 ? "" : "s"}. Select the red placeholder for details.`);
      }
      scheduleWorkspacePreferences();
    } catch (error) {
      setStatus(error.message || "Project load failed");
    }
  }

  async function initializeWorkspace() {
    await loadExportPreferences();
    const health = await checkProviderHealth();
    if (!health) {
      await restoreProject();
      return;
    }
    if (!health.projectsReady) {
      await restoreProject();
      setStatus("Project folders could not be scanned");
      return;
    }
    const preferredProject = state.projects.find((project) => project.id === state.workspacePreferences.lastActiveProjectId)
      || state.projects[0];
    if (preferredProject) {
      await loadProject(preferredProject.id);
      return;
    }
    const restored = await restoreProject();
    await createProject({ quick: true, preserveCanvas: restored, startup: true });
  }

  async function buildDraftPayload() {
    const references = getCompiledReferences();
    const videos = getCompiledVideoReferences();
    const payloadReferences = [];
    for (const reference of references) {
      payloadReferences.push({
        filename: reference.filename,
        instruction: reference.annotation.rawInstruction,
        imageDataUrl: await cropAnnotation(reference.asset, reference.annotation),
      });
    }
    for (const reference of videos) {
      payloadReferences.push({
        filename: reference.filename,
        instruction: `${reference.instruction} The attached image is a contact sheet sampled across the entire video. Infer only motion or temporal qualities supported by those samples.`,
        imageDataUrl: await buildVideoContactSheet(reference.asset),
      });
    }
    return {
      provider: els.providerInput.value,
      model: els.modelInput.value,
      imageDetail: els.imageDetailInput.value,
      objective: els.objectiveInput.value.trim(),
      draftingInstructions: els.formatInput.value.trim(),
      references: payloadReferences,
    };
  }

  function validateStructuredDraft(result, compiled) {
    const finalPrompt = String(result.finalPrompt || "").trim();
    if (!finalPrompt) throw new Error("The drafting model returned an empty prompt.");
    if (!Array.isArray(result.references)) throw new Error("The drafting model returned no structured reference analysis.");
    const expected = compiled.map((reference) => reference.filename);
    const expectedSet = new Set(expected);
    const returned = result.references.map((reference) => String(reference?.filename || ""));
    const returnedSet = new Set(returned);
    const duplicates = returned.filter((filename, index) => returned.indexOf(filename) !== index);
    const missing = expected.filter((filename) => !returnedSet.has(filename));
    const unknown = returned.filter((filename) => !expectedSet.has(filename));
    if (duplicates.length || missing.length || unknown.length || returned.length !== expected.length) {
      const details = [
        missing.length ? `missing ${missing.join(", ")}` : "",
        unknown.length ? `unknown ${[...new Set(unknown)].join(", ")}` : "",
        duplicates.length ? `duplicate ${[...new Set(duplicates)].join(", ")}` : "",
      ].filter(Boolean).join("; ");
      throw new Error(`Draft reference analysis did not match the submitted crops${details ? ` (${details})` : ""}.`);
    }
    const missingInPrompt = expected.filter((filename) => !finalPrompt.includes(filename));
    if (missingInPrompt.length) {
      throw new Error(`Draft omitted reference filename${missingInPrompt.length === 1 ? "" : "s"}: ${missingInPrompt.join(", ")}`);
    }
    const promptFilenames = finalPrompt.match(/\bR\d{2,}[A-Z]+\.png\b/g) || [];
    const unknownInPrompt = [...new Set(promptFilenames.filter((filename) => !expectedSet.has(filename)))];
    if (unknownInPrompt.length) throw new Error(`Draft cited unknown reference filename${unknownInPrompt.length === 1 ? "" : "s"}: ${unknownInPrompt.join(", ")}`);
    return finalPrompt;
  }

  function applyStructuredDraft(result, before, fingerprint) {
    const compiled = getAllCompiledReferences();
    const compiledByFilename = new Map(compiled.map((reference) => [reference.filename, reference]));
    const finalPrompt = validateStructuredDraft(result, compiled);
    (result.references || []).forEach((analysis) => {
      const reference = compiledByFilename.get(analysis.filename);
      if (!reference) return;
      if (reference.kind === "video") {
        reference.asset.videoDescription = analysis.description || reference.asset.videoDescription;
        reference.asset.videoUse = analysis.use || reference.asset.videoUse;
        reference.asset.videoAvoid = analysis.avoid || "";
        reference.asset.videoObservations = Array.isArray(analysis.observations) ? analysis.observations : [];
      } else {
        reference.annotation.description = analysis.description || reference.annotation.description;
        reference.annotation.use = analysis.use || reference.annotation.use;
        reference.annotation.avoid = analysis.avoid || "";
        reference.annotation.aiObservations = Array.isArray(analysis.observations)
          ? analysis.observations
          : [];
      }
    });
    state.aiDraft = {
      source: "vision-model",
      provider: result.provider || els.providerInput.value,
      model: result.model || els.modelInput.value,
      summary: result.summary || "",
      finalPrompt,
      originalPrompt: finalPrompt,
      edited: false,
      stale: false,
      fingerprint,
      generatedAt: new Date().toISOString(),
      responseId: result.responseId || null,
      usage: result.usage || null,
    };
    state.lastDraftError = "";
    renderPromptState();
    renderReferenceList();
    renderSelectionPanel();
    setActivePanelTab("prompt");
    if (els.shell.classList.contains("panel-collapsed")) togglePanel(false);
    pushHistory(before, { preserveDraft: true });
  }

  async function analyzeAndDraft() {
    if (state.draftController) {
      state.draftController.abort();
      setStatus("Cancelling analysis…");
      return;
    }
    const references = getAllCompiledReferences();
    if (!references.length) {
      setStatus("Annotate at least one reference crop first");
      return;
    }
    if (els.apiKeyInput.value.trim() && !(await saveProviderCredential())) return;
    const before = captureSnapshot();
    const fingerprint = draftFingerprint();
    const requestId = ++state.draftRequestId;
    const originalLabel = els.previewButton.textContent;
    const controller = new AbortController();
    state.draftController = controller;
    state.lastDraftError = "";
    renderPromptState();
    els.previewButton.textContent = "Cancel";
    setStatus(`Preparing ${references.length} crop${references.length === 1 ? "" : "s"}…`);
    try {
      const payload = await buildDraftPayload();
      if (controller.signal.aborted) throw new DOMException("Draft cancelled", "AbortError");
      if (fingerprint !== draftFingerprint()) throw new DOMException("Canvas changed while crops were being prepared", "AbortError");
      setStatus(`Analyzing with ${payload.model}…`);
      const response = await fetch("/api/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || `Drafting failed (${response.status})`);
      if (requestId !== state.draftRequestId || fingerprint !== draftFingerprint()) {
        const staleError = new Error("The AI response was discarded because the canvas changed while it was drafting. Retry with the current references.");
        staleError.name = "StaleDraftError";
        throw staleError;
      }
      applyStructuredDraft(result, before, fingerprint);
      setStatus(`Drafted with ${result.model || payload.model}`);
      checkProviderHealth();
    } catch (error) {
      if (error.name === "AbortError") setStatus("Analysis cancelled");
      else {
        console.error(error);
        state.lastDraftError = error.message || "Image-aware drafting failed";
        renderPromptState();
        setStatus(state.lastDraftError);
      }
    } finally {
      if (state.draftController === controller) state.draftController = null;
      els.previewButton.textContent = originalLabel;
    }
  }

  function dataUrlToBytes(dataUrl) {
    const base64 = dataUrl.split(",")[1] || "";
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    return bytes;
  }

  async function mediaSourceToBytes(source) {
    if (String(source).startsWith("data:")) return dataUrlToBytes(source);
    const response = await fetch(source);
    if (!response.ok) throw new Error(`Could not read local media for export (${response.status}).`);
    return new Uint8Array(await response.arrayBuffer());
  }

  async function buildExportFiles() {
    const references = getCompiledReferences();
    const videoReferences = getCompiledVideoReferences();
    const manifest = {
      schemaVersion: 1,
      exportedAt: new Date().toISOString(),
      objective: els.objectiveInput.value.trim(),
      draftingInstructions: els.formatInput.value.trim(),
      promptFile: "prompt.md",
      draft: state.aiDraft
        ? {
            source: state.aiDraft.source,
            provider: state.aiDraft.provider || null,
            model: state.aiDraft.model,
            generatedAt: state.aiDraft.generatedAt,
            responseId: state.aiDraft.responseId,
            summary: state.aiDraft.summary,
            usage: state.aiDraft.usage,
            edited: Boolean(state.aiDraft.edited),
            stale: Boolean(state.aiDraft.stale),
          }
        : null,
      references: [
        ...references.map(({ asset, annotation, filename }) => ({
          type: "image-crop",
          filename,
          sourceAssetName: asset.name,
          sourceReferenceNumber: asset.referenceNumber,
          annotationId: annotation.id,
          label: annotation.label,
          instruction: annotation.rawInstruction,
          description: annotation.description,
          use: annotation.use,
          avoid: annotation.avoid,
          observations: annotation.aiObservations || [],
        })),
        ...videoReferences.map(({ asset, filename, instruction }) => ({
          type: "whole-video",
          filename,
          sourceAssetName: asset.name,
          sourceReferenceNumber: asset.referenceNumber,
          durationSeconds: asset.duration,
          sourceUrl: asset.sourceUrl || null,
          sourceTitle: asset.sourceTitle || asset.name,
          extractor: asset.sourceExtractor || null,
          retrievedAt: asset.retrievedAt || null,
          instruction,
          description: asset.videoDescription,
          use: asset.videoUse,
          avoid: asset.videoAvoid,
          observations: asset.videoObservations || [],
        })),
      ],
    };
    const files = [
      { name: "prompt.md", data: state.aiDraft?.finalPrompt || buildPromptText() },
      { name: "manifest.json", data: `${JSON.stringify(manifest, null, 2)}\n` },
    ];
    for (const reference of references) {
      const crop = await cropAnnotation(reference.asset, reference.annotation);
      files.push({ name: reference.filename, data: dataUrlToBytes(crop) });
    }
    for (const reference of videoReferences) {
      files.push({ name: reference.filename, data: await mediaSourceToBytes(reference.asset.src) });
    }
    return files;
  }

  function validateExportFiles(files) {
    const references = getAllCompiledReferences();
    if (!references.length) throw new Error("Annotate at least one reference crop before exporting.");
    const expected = references.map((reference) => reference.filename);
    const expectedSet = new Set(expected);
    if (expectedSet.size !== expected.length) throw new Error("Reference filenames are not unique. Reopen the project and try again.");
    const names = files.map((file) => file.name);
    if (new Set(names).size !== names.length) throw new Error("Export package contains duplicate filenames.");
    const required = ["prompt.md", "manifest.json", ...expected];
    const missingFiles = required.filter((name) => !names.includes(name));
    const extraFiles = names.filter((name) => !required.includes(name));
    if (missingFiles.length || extraFiles.length) {
      throw new Error(`Export file set is invalid${missingFiles.length ? `; missing ${missingFiles.join(", ")}` : ""}${extraFiles.length ? `; unexpected ${extraFiles.join(", ")}` : ""}.`);
    }
    const prompt = String(files.find((file) => file.name === "prompt.md")?.data || "");
    const missingInPrompt = expected.filter((filename) => !prompt.includes(filename));
    if (missingInPrompt.length) throw new Error(`Prompt does not cite ${missingInPrompt.join(", ")}. Regenerate or restore the prompt before exporting.`);
    const compactNames = prompt.match(/\b(?:R\d{2,}[A-Z]+\.png|V\d{2,}\.(?:mp4|webm|mov|mkv))\b/g) || [];
    const unknownInPrompt = [...new Set(compactNames.filter((filename) => !expectedSet.has(filename)))];
    if (unknownInPrompt.length) throw new Error(`Prompt cites unknown crop${unknownInPrompt.length === 1 ? "" : "s"}: ${unknownInPrompt.join(", ")}.`);
    const manifestText = String(files.find((file) => file.name === "manifest.json")?.data || "");
    let manifest;
    try {
      manifest = JSON.parse(manifestText);
    } catch {
      throw new Error("Export manifest is not valid JSON.");
    }
    const manifestNames = (manifest.references || []).map((reference) => reference.filename);
    if (manifestNames.length !== expected.length || expected.some((filename) => !manifestNames.includes(filename))) {
      throw new Error("Export manifest does not match the current crop set.");
    }
    return { referenceCount: references.length, prompt };
  }

  function exportDataToBase64(data) {
    const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
    let binary = "";
    const chunkSize = 0x8000;
    for (let offset = 0; offset < bytes.length; offset += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
    }
    return btoa(binary);
  }

  async function copyTextToClipboard(text) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.append(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
  }

  async function exportPackage() {
    if (!state.currentProject) {
      setStatus("Open or create a project before exporting");
      setActivePanelTab("projects");
      if (els.shell.classList.contains("panel-collapsed")) togglePanel(false);
      return;
    }
    if (!state.assets.length) {
      setStatus("Add and annotate an image before exporting");
      return;
    }
    if (state.aiDraft?.stale) {
      setStatus(state.aiDraft.staleReason || "Prompt is out of date. Regenerate before exporting.");
      renderPromptState();
      setActivePanelTab("prompt");
      return;
    }
    els.exportButton.disabled = true;
    setStatus("Preparing export…");
    try {
      if (state.currentProject) {
        if (!(await saveCurrentProject({ quiet: true, refresh: false }))) throw new Error("Project save failed before export.");
        const files = await buildExportFiles();
        validateExportFiles(files);
        const response = await fetch(`/api/projects/${encodeURIComponent(state.currentProject.id)}/export`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            files: files.map((file) => ({ name: file.name, base64: exportDataToBase64(file.data) })),
            openFolder: state.exportPreferences.openFolder,
          }),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.error || "Project export failed");
        if (state.exportPreferences.copyPrompt) {
          const promptFile = files.find((file) => file.name === "prompt.md");
          if (promptFile) await copyTextToClipboard(String(promptFile.data));
        }
        const actions = [
          state.exportPreferences.copyPrompt ? "prompt copied" : "",
          result.folderOpened ? "folder opened" : "",
          state.exportPreferences.openFolder && !result.folderOpened ? "folder could not be opened" : "",
        ].filter(Boolean);
        setStatus(`${files.length} files saved in ${result.folder}${actions.length ? ` Â· ${actions.join(" Â· ")}` : ""}`);
      }
    } catch (error) {
      if (error?.name === "AbortError") setStatus("Export cancelled");
      else {
        console.error(error);
        setStatus(error.message || "Export failed");
      }
    } finally {
      els.exportButton.disabled = false;
    }
  }

  function setActivePanelTab(tab) {
    document.querySelectorAll(".panel-tab").forEach((button) => {
      button.classList.toggle("active", button.dataset.tab === tab);
    });
    els.promptTab.hidden = tab !== "prompt";
    els.selectionTab.hidden = tab !== "selection";
    els.projectsTab.hidden = tab !== "projects";
    els.settingsTab.hidden = tab !== "settings";
  }

  function togglePanel(collapsed) {
    els.shell.classList.toggle("panel-collapsed", collapsed);
    els.expandPanelButton.hidden = !collapsed;
  }

  function fitAll() {
    if (!state.assets.length) {
      state.scale = 1;
      state.panX = 80;
      state.panY = 70;
      renderTransform();
      scheduleSave();
      return;
    }
    const bounds = state.assets.reduce(
      (acc, asset) => ({
        left: Math.min(acc.left, asset.x),
        top: Math.min(acc.top, asset.y),
        right: Math.max(acc.right, asset.x + asset.width),
        bottom: Math.max(acc.bottom, asset.y + asset.height),
      }),
      { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity },
    );
    const rect = els.workspace.getBoundingClientRect();
    const padding = 70;
    const width = Math.max(1, bounds.right - bounds.left);
    const height = Math.max(1, bounds.bottom - bounds.top);
    state.scale = clamp(Math.min((rect.width - padding * 2) / width, (rect.height - padding * 2) / height), 0.1, 2.5);
    state.panX = (rect.width - width * state.scale) / 2 - bounds.left * state.scale;
    state.panY = (rect.height - height * state.scale) / 2 - bounds.top * state.scale;
    renderTransform();
    scheduleSave();
  }

  function deleteSelected() {
    if (!state.selected) return;
    const before = captureSnapshot();
    if (state.selected.type === "assets") {
      const selectedIds = new Set(state.selected.assetIds);
      state.assets = state.assets.filter((asset) => !selectedIds.has(asset.id));
      selectedIds.forEach((assetId) => els.scene.querySelector(`[data-asset-id="${assetId}"]`)?.remove());
    } else if (state.selected.type === "annotations") {
      const selectedIds = new Set(state.selected.annotationIds);
      state.assets.forEach((asset) => {
        asset.annotations = asset.annotations.filter((annotation) => !selectedIds.has(annotation.id));
      });
    } else if (state.selected.type === "asset") {
      const index = state.assets.findIndex((asset) => asset.id === state.selected.assetId);
      if (index >= 0) {
        const [asset] = state.assets.splice(index, 1);
        els.scene.querySelector(`[data-asset-id="${asset.id}"]`)?.remove();
      }
    } else if (state.selected.type === "annotation") {
      const result = findAnnotation(state.selected.annotationId);
      if (result) {
        result.asset.annotations = result.asset.annotations.filter((item) => item.id !== result.annotation.id);
        els.scene.querySelector(`[data-annotation-id="${result.annotation.id}"]`)?.remove();
      }
    }
    selectItem(null);
    updateEmptyState();
    renderReferenceList();
    pushHistory(before);
    setStatus("Deleted");
  }

  function duplicateSelected() {
    if (!state.selected) return;
    const before = captureSnapshot();
    if (state.selected.type === "assets") {
      const copies = getSelectedAssets().map((source) => {
        const copy = clone(source);
        copy.id = uid("asset");
        copy.referenceNumber = nextReferenceNumber();
        copy.name = `${source.name} copy`;
        copy.x += 24;
        copy.y += 24;
        copy.annotations = copy.annotations.map((annotation) => ({ ...annotation, id: uid("annotation") }));
        state.assets.push(copy);
        return copy;
      });
      state.selected = { type: "assets", assetIds: copies.map((asset) => asset.id) };
      state.selectedAssetIds = [...state.selected.assetIds];
    } else if (state.selected.type === "annotations") {
      const copies = getSelectedAnnotations().map(({ asset, annotation }) => {
        const copy = clone(annotation);
        copy.id = uid("annotation");
        copy.letter = annotationLetter(asset.annotations.length);
        copy.x = clamp(copy.x + 0.025, 0, 1 - copy.width);
        copy.y = clamp(copy.y + 0.025, 0, 1 - copy.height);
        asset.annotations.push(copy);
        return copy;
      });
      state.selected = { type: "annotations", annotationIds: copies.map((annotation) => annotation.id) };
      state.selectedAnnotationIds = [...state.selected.annotationIds];
    } else if (state.selected.type === "asset") {
      const source = findAsset(state.selected.assetId);
      if (!source) return;
      const copy = clone(source);
      copy.id = uid("asset");
      copy.referenceNumber = nextReferenceNumber();
      copy.name = `${source.name} copy`;
      copy.x += 24;
      copy.y += 24;
      copy.annotations = copy.annotations.map((annotation) => ({ ...annotation, id: uid("annotation") }));
      state.assets.push(copy);
      state.selected = { type: "asset", assetId: copy.id };
    } else if (state.selected.type === "annotation") {
      const result = findAnnotation(state.selected.annotationId);
      if (!result) return;
      const copy = clone(result.annotation);
      copy.id = uid("annotation");
      copy.letter = annotationLetter(result.asset.annotations.length);
      copy.x = clamp(copy.x + 0.025, 0, 1 - copy.width);
      copy.y = clamp(copy.y + 0.025, 0, 1 - copy.height);
      result.asset.annotations.push(copy);
      state.selected = { type: "annotation", assetId: result.asset.id, annotationId: copy.id };
    }
    renderAll();
    pushHistory(before);
    setStatus("Duplicated");
  }

  function nudgeSelected(key, largeStep) {
    if (!state.selected) return false;
    const before = captureSnapshot();
    const direction = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    }[key];
    if (!direction) return false;
    const multiplier = largeStep ? 10 : 1;
    if (state.selected.type === "assets") {
      getSelectedAssets().forEach((asset) => {
        asset.x += direction[0] * multiplier;
        asset.y += direction[1] * multiplier;
      });
    } else if (state.selected.type === "annotations") {
      getSelectedAnnotations().forEach(({ asset, annotation }) => {
        const dx = direction[0] * multiplier / asset.width;
        const dy = direction[1] * multiplier / asset.height;
        annotation.x = clamp(annotation.x + dx, 0, 1 - annotation.width);
        annotation.y = clamp(annotation.y + dy, 0, 1 - annotation.height);
      });
    } else if (state.selected.type === "asset") {
      const asset = findAsset(state.selected.assetId);
      if (!asset) return false;
      asset.x += direction[0] * multiplier;
      asset.y += direction[1] * multiplier;
    } else if (state.selected.type === "annotation") {
      const result = findAnnotation(state.selected.annotationId);
      if (!result) return false;
      const dx = direction[0] * multiplier / result.asset.width;
      const dy = direction[1] * multiplier / result.asset.height;
      result.annotation.x = clamp(result.annotation.x + dx, 0, 1 - result.annotation.width);
      result.annotation.y = clamp(result.annotation.y + dy, 0, 1 - result.annotation.height);
    }
    renderAll();
    pushHistory(before);
    setStatus(largeStep ? "Nudged 10 px" : "Nudged 1 px");
    return true;
  }

  function changeLayer(direction) {
    const assetId = state.selected?.type === "asset"
      ? state.selected.assetId
      : state.selected?.assetId;
    const index = state.assets.findIndex((asset) => asset.id === assetId);
    const nextIndex = clamp(index + direction, 0, state.assets.length - 1);
    if (index < 0 || nextIndex === index) return;
    const before = captureSnapshot();
    const [asset] = state.assets.splice(index, 1);
    state.assets.splice(nextIndex, 0, asset);
    renderAll();
    pushHistory(before);
    setStatus(direction > 0 ? "Brought forward" : "Sent backward");
  }

  els.workspace.addEventListener("wheel", (event) => {
    event.preventDefault();
    const rect = els.workspace.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    const worldX = (mouseX - state.panX) / state.scale;
    const worldY = (mouseY - state.panY) / state.scale;
    const nextScale = clamp(state.scale * Math.exp(-event.deltaY * 0.0014), 0.08, 6);
    state.panX = mouseX - worldX * nextScale;
    state.panY = mouseY - worldY * nextScale;
    state.scale = nextScale;
    renderTransform();
    scheduleSave();
  }, { passive: false });

  function annotationPoint(asset, clientX, clientY) {
    const point = screenToWorld(clientX, clientY);
    return {
      x: (point.x - asset.x) / asset.width,
      y: (point.y - asset.y) / asset.height,
    };
  }

  function resizeAsset(interaction, point, fromCenter) {
    const { asset, geometry, handle } = interaction;
    const ratio = geometry.width / geometry.height;
    const center = {
      x: geometry.x + geometry.width / 2,
      y: geometry.y + geometry.height / 2,
    };
    const opposite = {
      x: handle.includes("w") ? geometry.x + geometry.width : geometry.x,
      y: handle.includes("n") ? geometry.y + geometry.height : geometry.y,
    };
    const anchor = fromCenter ? center : opposite;
    const multiplier = fromCenter ? 2 : 1;
    const rawWidth = Math.abs(point.x - anchor.x) * multiplier;
    const rawHeight = Math.abs(point.y - anchor.y) * multiplier;
    let width = Math.max(rawWidth, rawHeight * ratio, 80);
    let height = width / ratio;
    if (height < 60) {
      height = 60;
      width = height * ratio;
    }
    if (fromCenter) {
      asset.x = center.x - width / 2;
      asset.y = center.y - height / 2;
    } else {
      asset.x = handle.includes("w") ? opposite.x - width : opposite.x;
      asset.y = handle.includes("n") ? opposite.y - height : opposite.y;
    }
    asset.width = width;
    asset.height = height;
  }

  function resizeAnnotation(interaction, point) {
    const { asset, annotation, geometry, handle } = interaction;
    const minWidth = Math.max(8 / asset.naturalWidth, 0.008);
    const minHeight = Math.max(8 / asset.naturalHeight, 0.008);
    let left = geometry.x;
    let top = geometry.y;
    let right = geometry.x + geometry.width;
    let bottom = geometry.y + geometry.height;
    if (handle.includes("w")) left = clamp(point.x, 0, right - minWidth);
    if (handle.includes("e")) right = clamp(point.x, left + minWidth, 1);
    if (handle.includes("n")) top = clamp(point.y, 0, bottom - minHeight);
    if (handle.includes("s")) bottom = clamp(point.y, top + minHeight, 1);
    Object.assign(annotation, {
      x: left,
      y: top,
      width: right - left,
      height: bottom - top,
    });
  }

  els.workspace.addEventListener("pointerdown", (event) => {
    if (event.button === 1 || state.isSpaceDown || state.tool === "hand") {
      state.interaction = {
        type: "pan",
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        panX: state.panX,
        panY: state.panY,
      };
      els.workspace.classList.add("is-panning");
      els.workspace.setPointerCapture(event.pointerId);
      return;
    }

    if (event.target.closest?.(".annotation-input-wrap")) return;
    const handleElement = event.target.closest?.(".transform-handle");
    const annotationElement = event.target.closest?.(".annotation");
    const assetElement = event.target.closest?.(".asset");

    if (state.tool === "region") {
      if (!assetElement) {
        setStatus("Draw the region inside an image");
        return;
      }
      const asset = findAsset(assetElement.dataset.assetId);
      const before = captureSnapshot();
      if (asset.type === "video") {
        selectItem({ type: "asset", assetId: asset.id });
        openVideoInstructionInput(asset, { before });
        setActivePanelTab("selection");
        return;
      }
      const start = screenToWorld(event.clientX, event.clientY);
      const annotation = createAnnotation(asset, start, start);
      asset.annotations.push(annotation);
      renderAnnotation(asset, annotation);
      state.interaction = { type: "region", pointerId: event.pointerId, asset, annotation, start, before };
      els.workspace.setPointerCapture(event.pointerId);
      return;
    }

    if (handleElement && annotationElement) {
      const result = findAnnotation(annotationElement.dataset.annotationId);
      if (!result) return;
      selectItem({ type: "annotation", assetId: result.asset.id, annotationId: result.annotation.id });
      state.interaction = {
        type: "resize-annotation",
        pointerId: event.pointerId,
        ...result,
        handle: handleElement.dataset.handle,
        geometry: clone({
          x: result.annotation.x,
          y: result.annotation.y,
          width: result.annotation.width,
          height: result.annotation.height,
        }),
        before: captureSnapshot(),
      };
      els.workspace.setPointerCapture(event.pointerId);
      return;
    }

    if (handleElement && assetElement) {
      const asset = findAsset(assetElement.dataset.assetId);
      selectItem({ type: "asset", assetId: asset.id });
      state.interaction = {
        type: "resize-asset",
        pointerId: event.pointerId,
        asset,
        handle: handleElement.dataset.handle,
        geometry: clone({ x: asset.x, y: asset.y, width: asset.width, height: asset.height }),
        before: captureSnapshot(),
      };
      els.workspace.setPointerCapture(event.pointerId);
      return;
    }

    if (annotationElement) {
      const result = findAnnotation(annotationElement.dataset.annotationId);
      if (!result) return;
      const additive = event.shiftKey || event.ctrlKey || event.metaKey;
      if (additive) {
        const nextIds = new Set(state.selectedAnnotationIds);
        if (nextIds.has(result.annotation.id)) nextIds.delete(result.annotation.id);
        else nextIds.add(result.annotation.id);
        const annotationIds = [...nextIds];
        selectItem(annotationIds.length > 1
          ? { type: "annotations", annotationIds }
          : annotationIds.length === 1
            ? { type: "annotation", assetId: findAnnotation(annotationIds[0])?.asset.id, annotationId: annotationIds[0] }
            : null);
        setActivePanelTab("selection");
        return;
      }
      if (state.selectedAnnotationIds.length > 1 && state.selectedAnnotationIds.includes(result.annotation.id)) {
        state.interaction = {
          type: "move-annotations",
          pointerId: event.pointerId,
          startPoint: screenToWorld(event.clientX, event.clientY),
          annotations: getSelectedAnnotations().map((entry) => ({
            ...entry,
            x: entry.annotation.x,
            y: entry.annotation.y,
          })),
          before: captureSnapshot(),
        };
        setActivePanelTab("selection");
        els.workspace.setPointerCapture(event.pointerId);
        return;
      }
      selectItem({ type: "annotation", assetId: result.asset.id, annotationId: result.annotation.id });
      const point = annotationPoint(result.asset, event.clientX, event.clientY);
      state.interaction = {
        type: "move-annotation",
        pointerId: event.pointerId,
        ...result,
        startPoint: point,
        geometry: clone({ x: result.annotation.x, y: result.annotation.y }),
        before: captureSnapshot(),
      };
      setActivePanelTab("selection");
      els.workspace.setPointerCapture(event.pointerId);
      return;
    }

    if (assetElement) {
      const asset = findAsset(assetElement.dataset.assetId);
      const additive = event.shiftKey || event.ctrlKey || event.metaKey;
      if (additive) {
        const nextIds = new Set(state.selectedAssetIds);
        if (nextIds.has(asset.id)) nextIds.delete(asset.id);
        else nextIds.add(asset.id);
        const assetIds = [...nextIds];
        selectItem(assetIds.length > 1
          ? { type: "assets", assetIds }
          : assetIds.length === 1
            ? { type: "asset", assetId: assetIds[0] }
            : null);
        return;
      }
      const point = screenToWorld(event.clientX, event.clientY);
      if (state.selectedAssetIds.length > 1 && state.selectedAssetIds.includes(asset.id)) {
        state.interaction = {
          type: "move-assets",
          pointerId: event.pointerId,
          startPoint: point,
          assets: getSelectedAssets().map((selectedAsset) => ({
            asset: selectedAsset,
            x: selectedAsset.x,
            y: selectedAsset.y,
          })),
          before: captureSnapshot(),
        };
        els.workspace.setPointerCapture(event.pointerId);
        return;
      }
      selectItem({ type: "asset", assetId: asset.id });
      state.interaction = {
        type: "move-asset",
        pointerId: event.pointerId,
        asset,
        offsetX: point.x - asset.x,
        offsetY: point.y - asset.y,
        before: captureSnapshot(),
      };
      els.workspace.setPointerCapture(event.pointerId);
      return;
    }

    const workspaceRect = els.workspace.getBoundingClientRect();
    const start = screenToWorld(event.clientX, event.clientY);
    const marquee = document.createElement("div");
    marquee.className = "selection-marquee";
    marquee.style.left = `${event.clientX - workspaceRect.left}px`;
    marquee.style.top = `${event.clientY - workspaceRect.top}px`;
    marquee.style.width = "0px";
    marquee.style.height = "0px";
    els.workspace.append(marquee);
    const startingIds = (event.shiftKey || event.ctrlKey || event.metaKey) ? [...state.selectedAssetIds] : [];
    if (!startingIds.length) selectItem(null);
    state.interaction = {
      type: "marquee",
      pointerId: event.pointerId,
      start,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startingIds,
      marquee,
    };
    els.workspace.setPointerCapture(event.pointerId);
  });

  els.workspace.addEventListener("pointermove", (event) => {
    const interaction = state.interaction;
    if (!interaction || interaction.pointerId !== event.pointerId) return;
    if (interaction.type === "pan") {
      state.panX = interaction.panX + event.clientX - interaction.startX;
      state.panY = interaction.panY + event.clientY - interaction.startY;
      renderTransform();
      return;
    }
    if (interaction.type === "move-asset") {
      const point = screenToWorld(event.clientX, event.clientY);
      interaction.asset.x = point.x - interaction.offsetX;
      interaction.asset.y = point.y - interaction.offsetY;
      renderAsset(interaction.asset);
      interaction.asset.annotations.forEach((annotation) => renderAnnotation(interaction.asset, annotation));
      return;
    }
    if (interaction.type === "move-assets") {
      const point = screenToWorld(event.clientX, event.clientY);
      const dx = point.x - interaction.startPoint.x;
      const dy = point.y - interaction.startPoint.y;
      interaction.assets.forEach((entry) => {
        entry.asset.x = entry.x + dx;
        entry.asset.y = entry.y + dy;
        renderAsset(entry.asset);
        entry.asset.annotations.forEach((annotation) => renderAnnotation(entry.asset, annotation));
      });
      return;
    }
    if (interaction.type === "marquee") {
      const current = screenToWorld(event.clientX, event.clientY);
      const left = Math.min(interaction.start.x, current.x);
      const top = Math.min(interaction.start.y, current.y);
      const right = Math.max(interaction.start.x, current.x);
      const bottom = Math.max(interaction.start.y, current.y);
      const workspaceRect = els.workspace.getBoundingClientRect();
      interaction.marquee.style.left = `${Math.min(interaction.startClientX, event.clientX) - workspaceRect.left}px`;
      interaction.marquee.style.top = `${Math.min(interaction.startClientY, event.clientY) - workspaceRect.top}px`;
      interaction.marquee.style.width = `${Math.abs(event.clientX - interaction.startClientX)}px`;
      interaction.marquee.style.height = `${Math.abs(event.clientY - interaction.startClientY)}px`;
      const hitIds = state.assets
        .filter((asset) => asset.x < right && asset.x + asset.width > left && asset.y < bottom && asset.y + asset.height > top)
        .map((asset) => asset.id);
      const assetIds = [...new Set([...interaction.startingIds, ...hitIds])];
      selectItem(assetIds.length > 1
        ? { type: "assets", assetIds }
        : assetIds.length === 1
          ? { type: "asset", assetId: assetIds[0] }
          : null);
      return;
    }
    if (interaction.type === "resize-asset") {
      resizeAsset(interaction, screenToWorld(event.clientX, event.clientY), event.altKey);
      renderAsset(interaction.asset);
      interaction.asset.annotations.forEach((annotation) => renderAnnotation(interaction.asset, annotation));
      return;
    }
    if (interaction.type === "move-annotation") {
      const point = annotationPoint(interaction.asset, event.clientX, event.clientY);
      interaction.annotation.x = clamp(
        interaction.geometry.x + point.x - interaction.startPoint.x,
        0,
        1 - interaction.annotation.width,
      );
      interaction.annotation.y = clamp(
        interaction.geometry.y + point.y - interaction.startPoint.y,
        0,
        1 - interaction.annotation.height,
      );
      renderAnnotation(interaction.asset, interaction.annotation);
      return;
    }
    if (interaction.type === "move-annotations") {
      const point = screenToWorld(event.clientX, event.clientY);
      const dx = point.x - interaction.startPoint.x;
      const dy = point.y - interaction.startPoint.y;
      interaction.annotations.forEach((entry) => {
        entry.annotation.x = clamp(entry.x + dx / entry.asset.width, 0, 1 - entry.annotation.width);
        entry.annotation.y = clamp(entry.y + dy / entry.asset.height, 0, 1 - entry.annotation.height);
        renderAnnotation(entry.asset, entry.annotation);
      });
      return;
    }
    if (interaction.type === "resize-annotation") {
      resizeAnnotation(interaction, annotationPoint(interaction.asset, event.clientX, event.clientY));
      renderAnnotation(interaction.asset, interaction.annotation);
      return;
    }
    if (interaction.type === "region") {
      const current = screenToWorld(event.clientX, event.clientY);
      const next = createAnnotation(interaction.asset, interaction.start, current);
      Object.assign(interaction.annotation, {
        x: next.x,
        y: next.y,
        width: next.width,
        height: next.height,
      });
      renderAnnotation(interaction.asset, interaction.annotation);
    }
  });

  function finishPointerInteraction(event) {
    const interaction = state.interaction;
    if (!interaction || interaction.pointerId !== event.pointerId) return;
    state.interaction = null;
    els.workspace.classList.remove("is-panning");
    if (interaction.type === "marquee") {
      interaction.marquee.remove();
      if (state.selectedAssetIds.length) setActivePanelTab("selection");
      setStatus(state.selectedAssetIds.length
        ? `${state.selectedAssetIds.length} image${state.selectedAssetIds.length === 1 ? "" : "s"} selected`
        : "Selection cleared");
    }
    if (interaction.type === "pan") scheduleSave();
    if (["move-asset", "move-assets", "resize-asset"].includes(interaction.type)) {
      pushHistory(interaction.before);
      setStatus(interaction.type === "resize-asset"
        ? "Image resized"
        : interaction.type === "move-assets"
          ? `${interaction.assets.length} images moved`
          : "Image moved");
    }
    if (["move-annotation", "move-annotations", "resize-annotation"].includes(interaction.type)) {
      pushHistory(interaction.before);
      renderReferenceList();
      renderSelectionPanel();
      setStatus(interaction.type === "resize-annotation"
        ? "Region resized"
        : interaction.type === "move-annotations"
          ? `${interaction.annotations.length} regions moved`
          : "Region moved");
    }
    if (interaction.type === "region") {
      const { asset, annotation } = interaction;
      const pixelWidth = annotation.width * asset.width * state.scale;
      const pixelHeight = annotation.height * asset.height * state.scale;
      if (pixelWidth < 8 || pixelHeight < 8) {
        asset.annotations = asset.annotations.filter((item) => item.id !== annotation.id);
        els.scene.querySelector(`[data-annotation-id="${annotation.id}"]`)?.remove();
        setStatus("Region was too small");
        return;
      }
      state.annotationCounter += 1;
      selectItem({ type: "annotation", assetId: asset.id, annotationId: annotation.id });
      openAnnotationInput(asset, annotation, { before: interaction.before });
    }
  }

  els.workspace.addEventListener("pointerup", finishPointerInteraction);
  els.workspace.addEventListener("pointercancel", finishPointerInteraction);

  els.workspace.addEventListener("dblclick", (event) => {
    if (event.ctrlKey) {
      event.preventDefault();
      els.fileInput.click();
      setStatus("Choose one or more reference images");
      return;
    }
    const annotationElement = event.target.closest?.(".annotation");
    if (!annotationElement || event.target.closest?.(".transform-handle")) return;
    const result = findAnnotation(annotationElement.dataset.annotationId);
    if (!result) return;
    selectItem({ type: "annotation", assetId: result.asset.id, annotationId: result.annotation.id });
    openAnnotationInput(result.asset, result.annotation, { editing: true, before: captureSnapshot() });
  });

  document.addEventListener("paste", (event) => {
    const target = event.target;
    if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return;
    const items = [...(event.clipboardData?.items || [])];
    const mediaItems = items.filter((item) => item.type.startsWith("image/") || item.type.startsWith("video/"));
    if (mediaItems.length) {
      event.preventDefault();
      mediaItems.forEach((item, index) => {
        const file = item.getAsFile();
        if (file) loadImageFile(new File([file], file.name || `Pasted reference ${index + 1}`, { type: file.type }));
      });
      return;
    }
    const text = event.clipboardData?.getData("text/plain")?.trim() || "";
    if (/^https?:\/\/\S+$/i.test(text)) {
      event.preventDefault();
      importVideoUrl(text);
    }
  });

  async function importVideoUrl(url) {
    if (!state.currentProject) {
      setStatus("Open or create a project before importing a video link");
      return;
    }
    setStatus("Downloading video link into the current projectâ€¦");
    try {
      const projectId = encodeURIComponent(state.currentProject.id);
      const directFile = /\.(mp4|webm|mov|m4v|mkv)(?:[?#]|$)/i.test(url);
      if (!directFile) return await importVideoPage(projectId, url);
      const response = await fetch(`/api/projects/${projectId}/videos/import-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.error || "Video link import failed");
      addVideo(result.src, result.name, { mimeType: result.mimeType, sourceFile: result.sourceFile });
    } catch (error) {
      console.error(error);
      setStatus(error.message || "Video link import failed");
    }
  }

  async function importVideoPage(projectId, url) {
    setStatus("Resolving public video page…");
    const created = await fetch(`/api/projects/${projectId}/video-jobs`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }) });
    const job = await created.json().catch(() => ({}));
    if (!created.ok) throw new Error(job.error || "Video job could not be created");
    while (true) {
      await new Promise((resolve) => window.setTimeout(resolve, 900));
      const response = await fetch(`/api/projects/${projectId}/video-jobs/${encodeURIComponent(job.id)}`, { cache: "no-store" });
      const status = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(status.error || "Video download status could not be read");
      if (status.state === "ready") { addVideo(status.result.src, status.result.name, { mimeType: status.result.mimeType, sourceFile: status.result.sourceFile, sourceUrl: status.result.sourceUrl, sourceTitle: status.result.title, sourceExtractor: status.result.extractor, retrievedAt: status.result.retrievedAt }); setStatus(`Video downloaded · ${status.result.name}`); return; }
      if (status.state === "failed" || status.state === "cancelled") throw new Error(status.error || `Video job ${status.state}`);
      setStatus(status.state === "resolving" ? "Resolving public video page…" : "Downloading public video…");
    }
  }

  els.workspace.addEventListener("dragover", (event) => {
    event.preventDefault();
  });

  els.workspace.addEventListener("drop", (event) => {
    event.preventDefault();
    [...event.dataTransfer.files].forEach(loadImageFile);
  });

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const isTyping = target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement;
    if (event.code === "Space" && !isTyping) {
      state.isSpaceDown = true;
      event.preventDefault();
    }
    if (isTyping) return;
    const modifier = event.ctrlKey || event.metaKey;
    if (modifier && event.key.toLowerCase() === "z") {
      event.preventDefault();
      event.shiftKey ? redo() : undo();
      return;
    }
    if (modifier && event.key.toLowerCase() === "y") {
      event.preventDefault();
      redo();
      return;
    }
    if (modifier && event.key.toLowerCase() === "d") {
      event.preventDefault();
      duplicateSelected();
      return;
    }
    if (modifier && event.key.toLowerCase() === "s") {
      event.preventDefault();
      saveCurrentProject();
      return;
    }
    if (modifier && event.key === "]") {
      event.preventDefault();
      changeLayer(1);
      return;
    }
    if (modifier && event.key === "[") {
      event.preventDefault();
      changeLayer(-1);
      return;
    }
    if (nudgeSelected(event.key, event.shiftKey)) {
      event.preventDefault();
      return;
    }
    if (event.key.toLowerCase() === "r") setTool("region");
    if (event.key.toLowerCase() === "v") setTool("select");
    if (event.key.toLowerCase() === "h") setTool("hand");
    if (event.key === "Enter") {
      if (state.selected?.type === "annotation") {
        const result = findAnnotation(state.selected.annotationId);
        if (result) openAnnotationInput(result.asset, result.annotation, { editing: true, before: captureSnapshot() });
      } else if (state.selected?.type === "asset") {
        const asset = findAsset(state.selected.assetId);
        if (asset?.type === "video") openVideoInstructionInput(asset, { before: captureSnapshot() });
      }
    }
    if (event.key === "Escape") {
      if (state.interaction?.before) {
        applySnapshot(state.interaction.before);
        state.interaction = null;
        els.workspace.classList.remove("is-panning");
        setStatus("Transform cancelled");
      }
      setTool("select");
    }
    if (event.key === "0") fitAll();
    if (event.key === "Delete" || event.key === "Backspace") deleteSelected();
  });

  document.addEventListener("keyup", (event) => {
    if (event.code === "Space") state.isSpaceDown = false;
  });

  document.querySelectorAll(".tool[data-tool]").forEach((button) => {
    button.addEventListener("click", () => setTool(button.dataset.tool));
  });
  document.querySelectorAll(".panel-tab").forEach((button) => {
    button.addEventListener("click", () => setActivePanelTab(button.dataset.tab));
  });

  els.emptyImportButton.addEventListener("click", () => els.fileInput.click());
  els.fileInput.addEventListener("change", () => {
    [...els.fileInput.files].forEach(loadImageFile);
    els.fileInput.value = "";
  });
  els.fitButton.addEventListener("click", fitAll);
  els.settingsButton.addEventListener("click", () => {
    setActivePanelTab("settings");
    if (els.shell.classList.contains("panel-collapsed")) togglePanel(false);
    els.aiSettings.open = true;
  });
  els.clearButton.addEventListener("click", () => {
    if (!state.assets.length) return;
    const before = captureSnapshot();
    state.assets = [];
    state.selected = null;
    state.selectedAssetIds = [];
    state.selectedAnnotationIds = [];
    els.scene.innerHTML = "";
    updateEmptyState();
    renderReferenceList();
    renderSelectionPanel();
    pushHistory(before);
    setStatus("Canvas cleared");
  });
  els.undoButton.addEventListener("click", undo);
  els.redoButton.addEventListener("click", redo);
  els.previewButton.addEventListener("click", analyzeAndDraft);
  els.mockDraftButton.addEventListener("click", compilePrompt);
  els.exportButton.addEventListener("click", exportPackage);
  els.copyPromptButton.addEventListener("click", async () => {
    await copyTextToClipboard(els.promptOutput.value);
    setStatus("Prompt copied");
  });
  let promptEditBefore = null;
  els.promptOutput.addEventListener("focus", () => { promptEditBefore = captureSnapshot(); });
  els.promptOutput.addEventListener("input", () => {
    if (!state.aiDraft) return;
    state.aiDraft.finalPrompt = els.promptOutput.value;
    state.aiDraft.edited = state.aiDraft.finalPrompt !== state.aiDraft.originalPrompt;
    state.lastDraftError = "";
    renderPromptState();
    scheduleSave();
  });
  els.promptOutput.addEventListener("change", () => {
    pushHistory(promptEditBefore, { preserveDraft: true });
    promptEditBefore = null;
  });
  els.restorePromptButton.addEventListener("click", () => {
    if (!state.aiDraft) return;
    const before = captureSnapshot();
    state.aiDraft.finalPrompt = state.aiDraft.originalPrompt;
    state.aiDraft.edited = false;
    state.lastDraftError = "";
    renderPromptState();
    pushHistory(before, { preserveDraft: true });
    setStatus("Original generated prompt restored");
  });
  els.regeneratePromptButton.addEventListener("click", analyzeAndDraft);
  els.retryDraftButton.addEventListener("click", analyzeAndDraft);
  els.collapsePanelButton.addEventListener("click", () => togglePanel(true));
  els.expandPanelButton.addEventListener("click", () => togglePanel(false));
  els.objectiveInput.addEventListener("input", () => {
    invalidateAIDraft("Objective changed. Regenerate before exporting.");
    scheduleSave();
  });
  els.formatInput.addEventListener("input", () => {
    invalidateAIDraft("Drafting instructions changed. Regenerate before exporting.");
    scheduleSave();
  });
  els.modelInput.addEventListener("change", () => {
    state.providerModel = els.modelInput.value;
    state.providerModels[els.providerInput.value] = els.modelInput.value;
    invalidateAIDraft("Vision model changed. Regenerate to use the selected model.");
    scheduleSave();
  });
  els.providerInput.addEventListener("change", () => {
    state.providerId = els.providerInput.value;
    els.apiKeyInput.value = "";
    renderProviderSettings();
    invalidateAIDraft("AI provider changed. Regenerate to use the selected provider.");
    scheduleSave();
  });
  els.apiKeyInput.addEventListener("input", () => {
    if (!els.apiKeyInput.value.trim()) {
      renderProviderSettings();
      return;
    }
    setProviderConnection("neutral", "Key ready to check", `Choose Save & connect to validate this ${selectedProvider()?.name || "provider"} key.`);
  });
  els.saveProviderButton.addEventListener("click", saveProviderCredential);
  els.removeProviderButton.addEventListener("click", removeProviderCredential);
  els.copyPromptOnExportInput.addEventListener("change", saveExportPreferences);
  els.openFolderOnExportInput.addEventListener("change", saveExportPreferences);
  els.createProjectButton.addEventListener("click", createProject);
  els.topCreateProjectButton.addEventListener("click", () => createProject({ quick: true }));
  els.openProjectsButton.addEventListener("click", async () => {
    setActivePanelTab("projects");
    if (els.shell.classList.contains("panel-collapsed")) togglePanel(false);
    await refreshProjects();
  });
  els.saveProjectButton.addEventListener("click", saveCurrentProject);
  els.refreshProjectsButton.addEventListener("click", refreshProjects);
  els.newProjectNameInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      createProject();
    }
  });
  els.imageDetailInput.addEventListener("change", () => {
    state.imageDetail = els.imageDetailInput.value;
    invalidateAIDraft("Image detail setting changed. Regenerate to apply it.");
    scheduleSave();
  });

  renderTransform();
  renderProviderOptions();
  renderProviderSettings();
  renderExportPreferences();
  updateEmptyState();
  renderReferenceList();
  renderProjectTabs();
  updateHistoryButtons();

  const benchmarkCount = clamp(
    Number.parseInt(new URLSearchParams(window.location.search).get("benchmark") || "0", 10) || 0,
    0,
    150,
  );
  if (benchmarkCount > 0) {
    window.__AI_CANVAS_BENCHMARK__ = {
      expected: benchmarkCount,
      startedAt: performance.now(),
      readyAt: null,
      durationMs: null,
    };
    setStatus(`Loading ${benchmarkCount}-image benchmark…`);
    for (let index = 0; index < benchmarkCount; index += 1) {
      addImage("./test-reference.svg", `Benchmark reference ${index + 1}`, { benchmark: true });
    }
  } else {
    initializeWorkspace();
  }
})();
