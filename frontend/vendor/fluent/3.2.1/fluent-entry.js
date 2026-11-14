/**
 * Local entry point for the pinned Fluent UI Web Components bundle.
 *
 * `web-components.min.js` is the official pre-bundled distribution. It
 * registers the Fluent elements and exposes the official `Fluent.setTheme`
 * helper as a browser global. No CDN request is made at runtime.
 */
import "./web-components.min.js";
export { webDarkTheme, webLightTheme } from "./tokens/lib/index.js";

export function applyFluentTheme(theme) {
  if (!globalThis.Fluent || typeof globalThis.Fluent.setTheme !== "function") {
    throw new Error("Fluent.setTheme is unavailable; the local bundle did not initialize.");
  }
  globalThis.Fluent.setTheme(theme);
}
