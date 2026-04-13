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

  /* ---- Tag badges ---- */

  const BADGE_CONTAINER_CLASS = "nbx-tag-badges";

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

  function syncBadges(cellWidget) {
    const node = cellWidget.node;
    const tags = getCellTags(cellWidget);
    let container = node.querySelector("." + BADGE_CONTAINER_CLASS);

    if (tags.length === 0) {
      if (container) {
        container.remove();
      }
      return;
    }

    if (!container) {
      container = document.createElement("div");
      container.className = BADGE_CONTAINER_CLASS;
      node.appendChild(container);
    }

    const labels = tags.map((t) => t.slice(4));
    const current = Array.from(container.children).map((el) => el.textContent);
    if (current.length === labels.length && current.every((t, i) => t === labels[i])) {
      return;
    }

    container.innerHTML = "";
    for (const label of labels) {
      const badge = document.createElement("span");
      badge.className = "nbx-tag-badge";
      badge.textContent = label;
      container.appendChild(badge);
    }
  }

  function watchCellMetadata(cellWidget) {
    const model = cellWidget.model;
    if (!model || model.__nbxBadgeWatch) {
      return;
    }
    model.__nbxBadgeWatch = true;

    if (model.metadataChanged) {
      model.metadataChanged.connect(() => syncBadges(cellWidget));
    }
    if (model.sharedModel?.changed) {
      model.sharedModel.changed.connect(() => syncBadges(cellWidget));
    }
  }

  function installTagBadges(panel) {
    const notebook = panel.content;
    if (notebook.__nbxBadgesInstalled) {
      return;
    }
    notebook.__nbxBadgesInstalled = true;

    function scanAll() {
      for (const widget of notebook.widgets) {
        if (widget && widget.node) {
          syncBadges(widget);
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
  }

  function installTagBadgesAll(tracker) {
    if (!tracker) {
      return;
    }

    if (typeof tracker.forEach === "function") {
      tracker.forEach((panel) => installTagBadges(panel));
    }

    if (!tracker.__nbxBadgesConnected) {
      tracker.__nbxBadgesConnected = true;
      tracker.widgetAdded.connect((_, panel) => installTagBadges(panel));
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
    installTagBadgesAll(tracker);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      void boot();
    }, { once: true });
  } else {
    void boot();
  }
})();
