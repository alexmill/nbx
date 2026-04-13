(() => {
  if (window.__nbxBooted) {
    return;
  }
  window.__nbxBooted = true;

  const COMMAND_ID = "nbx:preview-post";
  const THEME_NAME = "NBX";
  const TRACKER_PLUGIN_ID = "@jupyterlab/notebook-extension:tracker";
  const PALETTE_PLUGIN_ID = "@jupyterlab/apputils-extension:palette";
  const THEME_PLUGIN_ID = "@jupyterlab/apputils-extension:themes";

  function getConfig() {
    const node = document.getElementById("jupyter-config-data");
    if (!node || !node.textContent) {
      return {};
    }

    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      console.error("Failed to read Jupyter page config.", error);
      return {};
    }
  }

  function joinUrl(baseUrl, suffix) {
    const base = baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`;
    return `${base}${suffix}`;
  }

  function getService(app, pluginId) {
    return app?.pluginRegistry?._plugins?.get(pluginId)?.service ?? null;
  }

  function currentNotebookPanel(tracker, app) {
    const panel = tracker?.currentWidget ?? null;
    if (!panel) {
      return null;
    }

    const currentWidget = app?.shell?.currentWidget ?? null;
    return currentWidget === panel ? panel : panel;
  }

  function buildPreviewUrl(notebookPath) {
    const config = getConfig();
    return joinUrl(
      config.baseUrl || "/",
      `nbx-preview/render/${encodeURIComponent(notebookPath)}`
    );
  }

  function registerTheme(themeManager) {
    if (!themeManager) {
      return;
    }

    try {
      themeManager.register({
        name: THEME_NAME,
        displayName: THEME_NAME,
        isLight: true,
        themeScrollbars: false,
        load: () => Promise.resolve(undefined),
        unload: () => Promise.resolve(undefined),
      });
    } catch (error) {
      const message = String(error);
      if (!message.includes("Theme already registered")) {
        console.error("Failed to register the NBX theme.", error);
      }
    }

    Promise.resolve(themeManager.setPreferredLightTheme?.(THEME_NAME)).catch(() => {});
    Promise.resolve(themeManager.setTheme(THEME_NAME)).catch((error) => {
      console.error("Failed to activate the NBX theme.", error);
    });
  }

  function registerPreviewCommand(app, tracker) {
    if (app.commands.hasCommand(COMMAND_ID)) {
      return;
    }

    app.commands.addCommand(COMMAND_ID, {
      label: "Preview",
      isEnabled: () => Boolean(currentNotebookPanel(tracker, app)),
      execute: async () => {
        const panel = currentNotebookPanel(tracker, app);
        if (!panel?.context?.path) {
          return;
        }

        if (panel.context.model?.dirty && typeof panel.context.save === "function") {
          await panel.context.save();
        }

        window.open(buildPreviewUrl(panel.context.path), "_blank", "noopener,noreferrer");
      },
    });
  }

  function addPaletteItem(app) {
    const palette = getService(app, PALETTE_PLUGIN_ID);
    if (!palette || palette.__nbxPreviewAdded) {
      return;
    }

    palette.__nbxPreviewAdded = true;
    palette.addItem({
      command: COMMAND_ID,
      category: "NBX",
    });
  }

  function buildToolbarButton(app) {
    const item = document.createElement("div");
    item.className = "jp-Toolbar-item jp-nbx-toolbar-shell";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "jp-ToolbarButtonComponent jp-nbx-preview-button";
    button.innerHTML =
      '<span class="jp-ToolbarButtonComponent-label">Preview</span>';
    button.addEventListener("click", (event) => {
      event.preventDefault();
      void app.commands.execute(COMMAND_ID);
    });

    item.appendChild(button);
    return item;
  }

  function attachToolbarButton(panel, app) {
    const toolbarNode = panel?.toolbar?.node;
    if (!toolbarNode || toolbarNode.querySelector(".jp-nbx-preview-button")) {
      return;
    }

    toolbarNode.classList.add("jp-nbx-author-toolbar");
    toolbarNode.appendChild(buildToolbarButton(app));
  }

  /* ---- Cell tag bar ---- */

  const NBX_TAGS = [
    { id: "nbx-hide", label: "Hide cell" },
    { id: "nbx-collapse", label: "Collapse" },
    { id: "nbx-hide-input", label: "Hide input" },
    { id: "nbx-hide-output", label: "Hide output" },
    { id: "nbx-fig-hero", label: "Fig hero" },
    { id: "nbx-fig-full", label: "Fig full" },
    { id: "nbx-fig-inset", label: "Fig inset" },
    { id: "nbx-fig-fullscreen", label: "Fig fullscreen" },
  ];

  const TAG_BAR_CLASS = "nbx-tag-bar";

  function getCellTags(cellWidget) {
    try {
      const model = cellWidget.model;
      if (!model) {
        return [];
      }
      const tags =
        (typeof model.getMetadata === "function" && model.getMetadata("tags")) ||
        model.metadata?.tags ||
        [];
      return Array.isArray(tags) ? tags.filter((t) => t.startsWith("nbx-")) : [];
    } catch {
      return [];
    }
  }

  function getAllCellTags(cellWidget) {
    try {
      const model = cellWidget.model;
      if (!model) {
        return [];
      }
      const tags =
        (typeof model.getMetadata === "function" && model.getMetadata("tags")) ||
        model.metadata?.tags ||
        [];
      return Array.isArray(tags) ? [...tags] : [];
    } catch {
      return [];
    }
  }

  function setCellTags(cellWidget, tags) {
    const model = cellWidget.model;
    if (!model) {
      return;
    }
    if (typeof model.setMetadata === "function") {
      model.setMetadata("tags", tags);
    } else if (model.sharedModel && typeof model.sharedModel.setMetadata === "function") {
      model.sharedModel.setMetadata("tags", tags);
    }
  }

  function addCellTag(cellWidget, tagId) {
    const all = getAllCellTags(cellWidget);
    if (!all.includes(tagId)) {
      all.push(tagId);
      setCellTags(cellWidget, all);
    }
  }

  function removeCellTag(cellWidget, tagId) {
    const all = getAllCellTags(cellWidget);
    const filtered = all.filter((t) => t !== tagId);
    setCellTags(cellWidget, filtered);
  }

  function labelForTag(tagId) {
    const entry = NBX_TAGS.find((t) => t.id === tagId);
    return entry ? entry.label : tagId.replace("nbx-", "");
  }

  function closeAllDropdowns() {
    document.querySelectorAll(".nbx-tag-dropdown").forEach((el) => el.remove());
  }

  function buildTagPill(cellWidget, tagId) {
    const pill = document.createElement("span");
    pill.className = "nbx-tag-pill";
    pill.dataset.tagId = tagId;

    const label = document.createElement("span");
    label.className = "nbx-tag-pill-label";
    label.textContent = labelForTag(tagId);
    pill.appendChild(label);

    const remove = document.createElement("button");
    remove.className = "nbx-tag-pill-remove";
    remove.type = "button";
    remove.textContent = "\u00d7";
    remove.title = "Remove " + tagId;
    remove.addEventListener("click", (e) => {
      e.stopPropagation();
      removeCellTag(cellWidget, tagId);
      syncTagBar(cellWidget);
    });
    pill.appendChild(remove);

    return pill;
  }

  function buildAddButton(cellWidget) {
    const btn = document.createElement("button");
    btn.className = "nbx-tag-add-btn";
    btn.type = "button";
    btn.textContent = "+";
    btn.title = "Add tag";

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const existing = document.querySelector(".nbx-tag-dropdown");
      if (existing && existing.parentNode === btn.parentNode) {
        existing.remove();
        return;
      }
      closeAllDropdowns();
      showDropdown(cellWidget, btn);
    });

    return btn;
  }

  function showDropdown(cellWidget, anchorBtn) {
    const currentTags = getCellTags(cellWidget);
    const available = NBX_TAGS.filter((t) => !currentTags.includes(t.id));

    if (available.length === 0) {
      return;
    }

    const dropdown = document.createElement("div");
    dropdown.className = "nbx-tag-dropdown";

    for (const tag of available) {
      const item = document.createElement("button");
      item.className = "nbx-tag-dropdown-item";
      item.type = "button";
      item.textContent = tag.label;
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        addCellTag(cellWidget, tag.id);
        dropdown.remove();
        syncTagBar(cellWidget);
      });
      dropdown.appendChild(item);
    }

    document.body.appendChild(dropdown);

    const rect = anchorBtn.getBoundingClientRect();
    dropdown.style.position = "fixed";
    dropdown.style.top = (rect.bottom + 4) + "px";
    dropdown.style.left = rect.left + "px";

    const dismiss = (e) => {
      if (!dropdown.contains(e.target) && e.target !== anchorBtn) {
        dropdown.remove();
        document.removeEventListener("pointerdown", dismiss, true);
      }
    };
    window.setTimeout(() => {
      document.addEventListener("pointerdown", dismiss, true);
    }, 0);
  }

  function syncTagBar(cellWidget) {
    const node = cellWidget.node;
    const tags = getCellTags(cellWidget);
    const isActive = node.classList.contains("jp-mod-active");
    let bar = node.querySelector("." + TAG_BAR_CLASS);

    if (tags.length === 0 && !isActive) {
      if (bar) {
        bar.remove();
      }
      return;
    }

    if (!bar) {
      bar = document.createElement("div");
      bar.className = TAG_BAR_CLASS;
      node.insertBefore(bar, node.firstChild);
    }

    bar.innerHTML = "";

    for (const tagId of tags) {
      const pill = buildTagPill(cellWidget, tagId);
      if (!isActive) {
        pill.classList.add("nbx-tag-pill--readonly");
      }
      bar.appendChild(pill);
    }

    if (isActive) {
      bar.appendChild(buildAddButton(cellWidget));
    }
  }

  function watchCellMetadata(cellWidget) {
    const model = cellWidget.model;
    if (!model || model.__nbxTagWatch) {
      return;
    }
    model.__nbxTagWatch = true;

    if (model.metadataChanged) {
      model.metadataChanged.connect(() => syncTagBar(cellWidget));
    }
    if (model.sharedModel?.changed) {
      model.sharedModel.changed.connect(() => syncTagBar(cellWidget));
    }
  }

  function installTagBars(panel) {
    const notebook = panel.content;
    if (notebook.__nbxTagBarsInstalled) {
      return;
    }
    notebook.__nbxTagBarsInstalled = true;

    function scanAll() {
      for (const widget of notebook.widgets) {
        if (widget && widget.node) {
          syncTagBar(widget);
          watchCellMetadata(widget);
        }
      }
    }

    scanAll();

    if (notebook.model?.cells?.changed) {
      notebook.model.cells.changed.connect(() => {
        window.setTimeout(scanAll, 50);
      });
    }

    if (notebook.modelChanged) {
      notebook.modelChanged.connect(() => {
        window.setTimeout(scanAll, 100);
      });
    }

    if (notebook.activeCellChanged) {
      notebook.activeCellChanged.connect(() => {
        window.setTimeout(scanAll, 0);
      });
    }
  }

  function installTagBarsAll(tracker) {
    if (!tracker) {
      return;
    }

    if (typeof tracker.forEach === "function") {
      tracker.forEach((panel) => installTagBars(panel));
    }

    if (!tracker.__nbxTagBarsConnected) {
      tracker.__nbxTagBarsConnected = true;
      tracker.widgetAdded.connect((_, panel) => installTagBars(panel));
    }
  }

  /* ---- Toolbar buttons ---- */

  function installToolbarButtons(tracker, app) {
    if (!tracker) {
      return;
    }

    if (typeof tracker.forEach === "function") {
      tracker.forEach((panel) => attachToolbarButton(panel, app));
    }

    if (tracker.currentWidget) {
      attachToolbarButton(tracker.currentWidget, app);
    }

    if (!tracker.__nbxToolbarConnected) {
      tracker.__nbxToolbarConnected = true;
      tracker.widgetAdded.connect((_, panel) => attachToolbarButton(panel, app));
      tracker.currentChanged.connect(() => {
        if (tracker.currentWidget) {
          attachToolbarButton(tracker.currentWidget, app);
        }
      });
    }
  }

  async function boot() {
    const app = window.jupyterapp;
    if (!app) {
      window.setTimeout(boot, 120);
      return;
    }

    await app.started;
    try {
      await app.restored;
    } catch (error) {
      console.error("Jupyter restoration failed before NBX booted.", error);
    }

    const themeManager = getService(app, THEME_PLUGIN_ID);
    const tracker = getService(app, TRACKER_PLUGIN_ID);

    registerTheme(themeManager);
    registerPreviewCommand(app, tracker);
    addPaletteItem(app);
    installToolbarButtons(tracker, app);
    installTagBarsAll(tracker);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      void boot();
    }, { once: true });
  } else {
    void boot();
  }
})();
