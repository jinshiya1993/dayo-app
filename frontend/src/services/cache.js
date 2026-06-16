// Tiny in-memory cache that lives at module scope, so it survives React
// Router navigation (which unmounts/remounts page components) but is cleared
// on a full page reload or logout. Lets pages render instantly from the last
// fetched data, then revalidate quietly in the background.
const store = new Map();

export function getCached(key) {
  return store.has(key) ? store.get(key) : undefined;
}

export function setCached(key, value) {
  store.set(key, value);
}

// Drop a single entry (e.g. after a mutation) so the next read refetches.
export function clearCached(key) {
  store.delete(key);
}

// Call on logout so the next user never sees the previous user's data.
export function clearCache() {
  store.clear();
}
