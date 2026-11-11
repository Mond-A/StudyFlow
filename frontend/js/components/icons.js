/** Tiny wrapper around Lucide's global icon renderer. */

export function icon(name, className = "") {
  const safeName = String(name || "circle").replace(/[^a-z0-9-]/gi, "");
  return `<i data-lucide="${safeName}" class="icon ${className}" aria-hidden="true"></i>`;
}

export function refreshIcons(root = document) {
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    try {
      window.lucide.createIcons({
        root,
        attrs: { "stroke-width": 1.8 },
      });
    } catch {
      // Icons are decorative; never break a page over them.
    }
  }
}
