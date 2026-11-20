# Security Policy

## Supported versions

StudyFlow is an actively developed MVP. Security fixes are applied to the
latest code on the `main` branch only.

| Version / branch | Security support |
| --- | --- |
| `main` (latest) | Best-effort fixes |
| Older commits, forks, and feature branches | Not supported |

The application currently reports the version `1.1.1`. This is not an LTS
release and no backport or fixed response-time commitment is made.

## Reporting a vulnerability

Please do not publish exploitable details, credentials, personal data, or
screenshots containing real user data in a public issue.

Preferred route:

1. Open the GitHub **Security** tab of the repository.
2. If **Report a vulnerability** (GitHub Private Vulnerability Reporting) is
   available, use it to open a private draft advisory.
3. If that option is not available, contact the maintainer through the public
   contact method shown on their GitHub profile and ask for a private reporting
   channel. A public issue may only ask for that channel; it must not contain
   vulnerability details.

There is no dedicated security email address or guaranteed response window.
Reports will be reviewed on a best-effort basis.

## What to include

- A short description of the issue and its potential impact.
- The affected route, file, configuration, or commit.
- Minimal reproduction steps using synthetic accounts and data.
- Whether the issue affects logged-in accounts, guest mode, uploads, email
  verification, session handling, or deployment configuration.
- Any suggested mitigation, if known.

Never include:

- Real passwords, session cookies, `SECRET_KEY`, SMTP credentials, or AI API
  keys.
- Production database files, uploads, backups, or `.env` contents.
- Real email addresses, student names, school data, or other personal data.
- Server addresses, private domains, or internal infrastructure details.

Use placeholders such as `user@example.invalid` and synthetic data instead.

## Scope

In scope:

- StudyFlow application code and authentication/session behavior.
- Email registration, verification, login, and account isolation.
- Guest-mode boundaries and explicit guest-to-account import.
- Upload validation and per-user upload access.
- The checked-in deployment files and documented production configuration.

Out of scope:

- Vulnerabilities in third-party packages or AI providers; report those to the
  upstream project/provider. A StudyFlow-specific issue caused by a dependency
  is still useful to report here.
- Social engineering, physical access, or compromised maintainer accounts.
- Volumetric denial-of-service against a host or network.
- Issues that require access to a production server or its secrets.
- General feature requests or documentation typos (use a normal issue).

## Security maintenance limitations

StudyFlow is a small educational project, not a commercial security product.
It does not provide a bug bounty, a 24/7 security team, a formal audit, or
enterprise compliance certification. Current protections include scrypt
password hashing, email verification, session security, same-origin checks,
per-user query scoping, upload ownership checks, and shared login rate
limiting backed by SQLite.

Known limitations:

- There is no two-factor authentication, password-reset flow, or account
  recovery workflow.
- Email delivery depends on the configured SMTP provider; the console mail
  backend is for local development only.
- Guest data lives in the browser's IndexedDB and is not backed up by the
  server. Clearing browser data may remove it.
- Automatic scheduled backups are not installed by this repository. Operators
  must run and verify the documented backup scripts themselves.
- A force-pushed or deleted Git ref does not instantly remove old objects from
  GitHub's server-side caches, reflogs, forks, or backups.

## Deployment expectations

Before exposing StudyFlow to the public internet, operators should follow
[`docs/DEPLOY_DEBIAN_ARM64.md`](docs/DEPLOY_DEBIAN_ARM64.md), including HTTPS,
`SESSION_COOKIE_SECURE=true`, a single trusted reverse proxy with
`TRUST_PROXY=true`, SMTP delivery, file permissions, and tested database and
upload backups. The repository does not install a production server, reverse
proxy, TLS certificate, or scheduled backup unit automatically.
