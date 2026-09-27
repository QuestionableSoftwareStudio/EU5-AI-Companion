# Self-update design

EU5 AI Companion uses GitHub Releases as the distribution source for application updates.

## Goals

- The running application must never overwrite its own files.
- A failed update must leave the last working version launchable.
- Every downloaded package must be verified before activation.
- User data, API keys, campaign databases and configuration stay outside the versioned application directory.

## Proposed install layout

```text
EU5 AI Companion/
  EU5 AI Companion.exe        # stable launcher/updater
  current.json
  app/
    0.1.0/
      EU5 AI Companion App.exe
    0.1.1/
      EU5 AI Companion App.exe
```

The launcher owns update checks. Application versions are installed side-by-side.

## Release manifest

Each stable release will publish a small JSON manifest containing at least:

```json
{
  "schema": 1,
  "channel": "stable",
  "version": "0.1.1",
  "launcher_protocol": 1,
  "package_url": "https://github.com/QuestionableSoftwareStudio/EU5-AI-Companion/releases/download/v0.1.1/EU5-AI-Companion-0.1.1-win-x64.zip",
  "sha256": "<sha256>"
}
```

## Update flow

1. Launcher reads the currently active version.
2. Launcher fetches the stable update manifest.
3. If a newer compatible version exists, it downloads the release ZIP.
4. Launcher verifies the SHA-256.
5. The ZIP is safely extracted into a new version directory.
6. The new executable is validated.
7. `current.json` is atomically switched to the new version.
8. Launcher starts that version.
9. If any step fails, the previous version remains active.

## Rollback

Because versions are side-by-side, rollback is just an atomic change of `current.json` to the previous known-good version.

Automatic cleanup of old versions can retain the current and one previous release.

## Release source

GitHub Actions will eventually build the Windows artifact and GitHub Releases will host:

- the versioned application ZIP,
- the update manifest,
- SHA-256 checksum metadata,
- release notes.

The updater should not depend on mutable files inside the application bundle itself.
