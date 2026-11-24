export function createConfigPreview(host) {
  const panel = document.createElement("section");
  panel.className = "config-preview";
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
  generate.disabled = true;
  panel.append(applicability, tool, warning, ack, ackLabel, generate);
  host.append(panel);

  ack.addEventListener("change", () => {
    generate.disabled = !ack.checked;
  });

  function update(plan) {
    applicability.textContent = plan.applicability_label || "";
    tool.textContent = plan.tool_label || "";
    const mismatch = (plan.warnings || []).find((item) => item.code === "applicability_mismatch");
    warning.hidden = !mismatch;
    if (mismatch) {
      warning.dataset.i18n = "wb.error.applicability_ack_required";
      warning.dataset.ackId = mismatch.ack_id;
      ack.checked = false;
      generate.disabled = true;
    }
  }

  return { panel, update };
}