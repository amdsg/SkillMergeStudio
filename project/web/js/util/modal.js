export function openModal(modal) {
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");
}

export function closeModal(modal) {
  modal.classList.add("hidden");
  document.body.classList.remove("modal-open");
}