import { createExportPlatforms } from "/js/views/export-platforms.js";
import { createExportPreview } from "/js/views/export-preview.js";
import { createExportResults } from "/js/views/export-results.js";
import { t } from "/js/i18n/index.js";

export function createExportController({ el, state, api }) {
  const platformsPanel = createExportPlatforms({
    root: el.exportPlatforms,
    getItems: () => state.platforms,
    getDefault: () => state.platform,
    onSelectionChange: () => {}
  });
  const previewPanel = createExportPreview({ root: el.exportPreview });
  const resultsPanel = createExportResults({ root: el.exportResults });

  async function previewFormats() {
    if (!state.artifact) {
      el.exportStatus.textContent = t("export.needMerge");
      return;
    }
    const platforms = platformsPanel.getSelected();
    if (!platforms.length) {
      el.exportStatus.textContent = t("export.noPlatform");
      return;
    }
    el.exportPreviewButton.disabled = true;
    el.exportStatus.textContent = t("list.loading");
    try {
      const result = await api("/api/export/preview", {
        method: "POST",
        body: JSON.stringify({
          artifact_id: state.artifact.artifact_id,
          platforms,
          mode: el.exportMode.value,
          length_mode: el.lengthMode.value,
          profile: el.profile.value
        })
      });
      previewPanel.render(result);
      el.exportStatus.textContent = "";
    } catch (error) {
      previewPanel.showError(error.message);
      el.exportStatus.textContent = error.message;
    } finally {
      el.exportPreviewButton.disabled = false;
    }
  }

  return {
    attach() {
      el.exportPreviewButton.addEventListener("click", previewFormats);
      el.exportMode.addEventListener("change", () => platformsPanel.setMode(el.exportMode.value));
    },
    render() {
      platformsPanel.render();
    },
    setDefault(platformId) {
      platformsPanel.setDefault(platformId);
      platformsPanel.render();
    },
    getSelectedItems() {
      return platformsPanel.getSelectedItems();
    },
    getSelected() {
      return platformsPanel.getSelected();
    },
    renderResults(result) {
      resultsPanel.render(result);
    },
    resetResults() {
      resultsPanel.reset();
      previewPanel.reset();
    },
    onLang() {
      platformsPanel.render();
    }
  };
}