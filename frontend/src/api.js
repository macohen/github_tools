/**
 * Get the base URL for API calls.
 * 
 * In web mode (Vite dev server), API calls go to /api/* and get proxied.
 * In Electron production mode, the frontend is loaded from file:// so we
 * need an absolute URL to the backend server.
 */
export function getApiBase() {
  // Electron injects the backend port via main process
  if (typeof window !== 'undefined' && window.__BACKEND_PORT__) {
    return `http://127.0.0.1:${window.__BACKEND_PORT__}`;
  }
  // Web mode: use relative URLs (Vite proxy handles it)
  return '';
}

/**
 * Convenience wrapper for fetch that prepends the API base URL.
 */
export function apiFetch(path, options) {
  return fetch(`${getApiBase()}${path}`, options);
}
