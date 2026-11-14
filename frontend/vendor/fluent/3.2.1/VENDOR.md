# Fluent UI Web Components — vendored dependency

Pinned and stored locally so production never depends on a third-party CDN.

| Package | Version | Role |
| --- | --- | --- |
| `@fluentui/web-components` | `3.2.1` | Official pre-built browser bundle |
| `@fluentui/tokens` | `1.0.0-alpha.24` | Official Fluent 2 light/dark theme token objects |
| `@microsoft/fast-element` | `3.0.0` | Peer runtime bundled inside `web-components.min.js` |
| `@microsoft/focusgroup-polyfill` | `1.5.0` | Peer runtime bundled inside `web-components.min.js` |
| `tslib` | `2.8.1` | Runtime dependency bundled inside `web-components.min.js` |

## Source

- https://www.npmjs.com/package/@fluentui/web-components/v/3.2.1
- https://www.npmjs.com/package/@fluentui/tokens/v/1.0.0-alpha.24
- https://github.com/microsoft/fluentui

## Contents

- `web-components.min.js` — `@fluentui/web-components@3.2.1/dist/web-components.min.js`
- `tokens/lib/**/*.js` — ESM output of `@fluentui/tokens@1.0.0-alpha.24`
- `tokens/lib/index.js` — exports `webLightTheme` and `webDarkTheme`
- `fluent-entry.js` — tiny local bridge exposing the official global `setTheme` as an ESM function

The unminified source bundle and source maps are intentionally not shipped. The
minified bundle is 266,811 bytes and includes the peer runtimes listed above.

## Integrity

`SHA-256(web-components.min.js)`:

```text
e98e0d8fd605ad159602c6a1eba5d1e1804737c1eb2e5e6ef38d4c16b9fcd24d
```

## Reproduction

```powershell
npm pack @fluentui/web-components@3.2.1
npm pack @fluentui/tokens@1.0.0-alpha.24
```

Then copy the files listed above. Do not use `@latest` in production. Upgrade
only after running the component lab at all supported breakpoints.

## Licensing

See `THIRD_PARTY_NOTICES.md` and the license files in this directory. All
packages are MIT-licensed Microsoft/Fluent UI projects.
