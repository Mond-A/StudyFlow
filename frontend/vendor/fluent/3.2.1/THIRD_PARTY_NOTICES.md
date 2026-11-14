# Third-party notices

This directory contains code from Microsoft's Fluent UI project and its bundled
runtime dependencies. All listed packages are distributed under the MIT License.

| Component | Version | License | Project |
| --- | --- | --- | --- |
| `@fluentui/web-components` | 3.2.1 | MIT | https://github.com/microsoft/fluentui |
| `@fluentui/tokens` | 1.0.0-alpha.24 | MIT | https://github.com/microsoft/fluentui |
| `@microsoft/fast-element` | 3.0.0 | MIT | https://github.com/microsoft/fast |
| `@microsoft/focusgroup-polyfill` | 1.5.0 | MIT | https://github.com/microsoft/fast |
| `tslib` | 2.8.1 | 0BSD | https://github.com/microsoft/tslib |

`web-components.min.js` is the official pre-bundled distribution. It includes
the Fast Element and focus-group runtimes; their license texts are represented
by the Microsoft MIT license in `LICENSE-fluent-mit.txt`. The `tslib` license is
included separately in `LICENSE-tslib.txt`.

The Fluent design tokens are consumed through the official
`@fluentui/tokens@1.0.0-alpha.24` ESM files in `tokens/lib/`.
