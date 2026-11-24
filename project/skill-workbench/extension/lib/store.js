const state = {
  locale: "zh",
  selection: new Set(),
  targets: [],
};

const listeners = new Set();

export function getState() {
  return state;
}

export function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify() {
  for (const listener of listeners) {
    listener(state);
  }
}

export function setLocale(locale) {
  state.locale = locale;
  notify();
}

export function toggleSelection(id) {
  if (state.selection.has(id)) {
    state.selection.delete(id);
  } else {
    state.selection.add(id);
  }
  notify();
}

export function setTargets(targets) {
  state.targets = Array.isArray(targets) ? targets : [];
  notify();
}