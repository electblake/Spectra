---
parent_prompt: |-
  describe coding agent instructions that will define the feature spec for implementing the Update checker functionality and dialog and behavour so that its code ready snippets full and very concisely can instruct coding agents on implementing the same feature in another project.
---

# Extras > Check for Updates

Implement the existing app’s manual **Check for Updates** feature using GitHub Releases. Follow local architecture and UI conventions; keep networking off the UI thread. Use the app’s name/version and repository configuration.

## Feature requirements

- Add an **Updates** section: installed-version label, **Check for Updates**, **View Releases** (opens `https://github.com/{owner}/{repo}/releases`).
- Checking opens a window-modal **Software Update** dialog (minimum width 460) with wrapped status text, progress bar, **Download Update**, **Quit and Install**, **Close**.
- Each check clears previous availability, installer-ready state, and installer path. Fetch `https://api.github.com/repos/{owner}/{repo}/releases/latest` with a 30-second timeout and headers `Accept: application/vnd.github+json`, `User-Agent: {APP_NAME}/{APP_VERSION}`, and the project’s GitHub API version.
- Strip one leading `v` from `tag_name`; compare numeric version tuples. Show `Installed: {installed} · Latest: {latest}`, plus **Update available** when strictly newer, otherwise **Up to date**.
- Download only the exact installer asset below into `platformdirs.user_cache_path(APP_NAME, appauthor=False) / "updates"`, retaining its filename. Create the directory; stream 256 KiB chunks, reporting downloaded bytes against `asset["size"]`.
- Checking and initial download progress are indeterminate; subsequent download progress uses a 0–1000 scale.
- While checking/downloading, disable competing app operations and all dialog buttons; block Escape, Close, and title-bar dismissal.
- Download is enabled only when idle, a newer release exists, and no installer is ready. Install is enabled only when idle with a completed installer. Close is enabled only when idle.
- On completion show **Download complete. Quit and install when ready.** and 100% progress. Ordinary dismissal never installs.
- **Quit and Install** records the installer path and requests normal app shutdown. Launch the installer only after the event loop returns.
- Use stable installer identity and upgrade location. No startup checks, scheduling, cancellation, automatic installation/relaunch, retries, exception handling, fallback assets/providers, or custom failure paths. Let failures surface naturally. Do not edit README files.

## Essential Python/PySide6 logic

```python
def version_tuple(value):
    return tuple(int(part) for part in value.split("."))

version = release["tag_name"].removeprefix("v")
available = version_tuple(version) > version_tuple(APP_VERSION)

name = (
    f"{APP_NAME}-{version}-{platform.system().lower()}-"
    f"{platform.machine().lower()}-Setup.exe"
)
asset = next(a for a in release["assets"] if a["name"] == name)

download_button.setEnabled(not busy and available and not ready)
install_button.setEnabled(not busy and ready)
close_button.setEnabled(not busy)

progress.setRange(0, 0 if current == 0 else 1000)
progress.setValue(round(current / total * 1000))
```

```python
# Quit and Install: save path, then use the app's normal shutdown.
window.pending_installer = installer_path
window.close()

# Bootstrap:
result = app.exec()
if window.pending_installer is not None:
    os.startfile(window.pending_installer)
return result
```

Initialize `pending_installer = None`. Retain workers until finished; deliver results/progress through Qt signals and update widgets on the UI thread.

## Acceptance checks

Verify numeric version ordering, exact asset selection, responsive networking, progress/button states, blocked busy dismissal, ordinary close without installation, and installer launch after event-loop exit.
