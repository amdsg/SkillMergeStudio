export function createConfigPreview(host, client) {
  const panel = document.createElement("section");
  panel.className = "config-preview";
  const files = document.createElement("input");
  files.type = "text";
  files.dataset.i18nPlaceholder = "wb.convert.search.placeholder";
  const applicability = document.createElement("p");
  applicability.dataset.role = "applicability";
  const tool = document.createElement("p");
  tool.dataset.role = "tool";
  const warning = document.createElement("p");
  warning.dataset.role = "applicability-warning";
  warning.hidden = true;
  const ack = document.createElement("input");
  ack.type = "checkbox";
  ack.id = "wb-ack-applicability";
  const ackLabel = document.createElement("label");
  ackLabel.htmlFor = ack.id;
  ackLabel.dataset.i18n = "wb.fix.ack_applicability";
  const generate = document.createElement("button");
  generate.type = "button";
  generate.dataset.i18n = "wb.button.preview";
  panel.append(files, applicability, tool, warning, ack, ackLabel, generate);
  host.append(panel);

  function update(plan) {
    applicability.textContent = plan.applicability_label || "";
    tool.textContent = plan.tool_label || "";
    const mismatch = (plan.warnings || []).find((item) => item.code === "applicability_mismatch");
    warning.hidden = !mismatch;
    if (mismatch) {
      warning.dataset.i18n = "wb.error.applicability_ack_required";
    }
  }

  generate.addEventListener("click", async () => {
    try {
      const names = files.value.split(",").map((s) => s.trim()).filter(Boolean);
      const plan = await client.preview({ files: names, target_tool: "claude_code", target_path: "" });
      update(plan);
    } catch (error) {
      applicability.textContent = error.code || "E_INTERNAL";
    }
  });

  return { panel, update };
}
