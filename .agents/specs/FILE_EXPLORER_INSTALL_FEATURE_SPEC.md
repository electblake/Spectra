---
original_prompt: >-
  describe coding agent instructions that will define the feature spec for implementing the Extras > Install in File Explorer so that its code ready snippets full and very concisely can instruct coding agents on implementing the same feature in another project.
---

# Extras > Install in File Explorer

Implement **Extras > Install in File Explorer**, matching the behavior below. Adapt names and imports to the target project; preserve its existing UI and worker patterns.

## Feature requirements

- Under **Extras**, add a **File Explorer** group, explanatory text, and **Install in File Explorer** button.
- Register **Open in {APP_NAME}** for folders, folder backgrounds, and drives.
- Write per-user registry entries under `HKEY_CURRENT_USER\Software\Classes`; require no administrator elevation.
- Use absolute launcher and icon paths. Quote every command argument.
- Reinstall by overwriting the same registry values.
- Run installation through the existing background-task mechanism. Disable conflicting controls while busy; show **Installed in File Explorer** only after successful completion.
- Explorer launches the app with the selected directory as its first positional argument. Populate the folder field without automatically starting processing.
- Implement only installation. Add no uninstall UI, elevation, retries, exception handling, fallback launchers, or custom validation paths.

## Registry implementation

Place this module alongside the application's other integration services. Replace `YourApp`, `your_package`, and the icon location with the target project's actual values.

```python
import sys
from pathlib import Path

APP_NAME = "YourApp"
APP_MODULE = "your_package"
ICON_NAME = f"{APP_NAME}.ico"

CONTEXTS = (
    (r"Software\Classes\Directory\shell", "%1"),
    (r"Software\Classes\Directory\Background\shell", "%V"),
    (r"Software\Classes\Drive\shell", "%1"),
)


def install():
    import winreg

    executable = str(Path(sys.executable).resolve())
    if getattr(sys, "frozen", False):
        launcher = [executable]
        icon_root = Path(sys._MEIPASS)
    else:
        launcher = [executable, "-I", "-m", APP_MODULE]
        icon_root = Path(__file__).resolve().parents[1]

    icon = f'"{icon_root / ICON_NAME}"'

    for root, target in CONTEXTS:
        menu_key = rf"{root}\{APP_NAME}"
        command = " ".join(f'"{part}"' for part in [*launcher, target])
        print(f"File Explorer command ({root}): {command}")

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, menu_key, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"Open in {APP_NAME}")
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon)

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            menu_key + r"\command",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)

    print(f"[OK] Installed {len(CONTEXTS)} File Explorer context menu entries.")
    return 0
```

The source launcher requires the package installed in the selected interpreter because `-I` excludes the working directory. Bundle the `.ico` at the PyInstaller extraction root for packaged execution. The packaged branch assumes PyInstaller; adapt it to the target project's actual packaging runtime when different.

## PySide6 UI

Insert into the existing Extras layout:

```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QPushButton, QVBoxLayout

explorer = QGroupBox("File Explorer")
form = QVBoxLayout(explorer)

hint = QLabel(
    f"Add Open in {APP_NAME} to right-click menus "
    "for folders, folder backgrounds, and drives."
)
hint.setWordWrap(True)
form.addWidget(hint)

install = QPushButton("Install in File Explorer")
install.clicked.connect(self.controller.installExplorer)
form.addWidget(install, alignment=Qt.AlignmentFlag.AlignLeft)
layout.addWidget(explorer)
```

Connect through the existing controller task lifecycle (`Slot` is imported from `PySide6.QtCore`; `integrations` refers to the registry module above):

```python
@Slot()
def installExplorer(self):
    self._launch("install", lambda report: integrations.install())
```

In its successful-result handler:

```python
elif self._kind == "install":
    self._status = "Installed in File Explorer"
```

These controller snippets assume an existing `_launch(kind, operation)` mechanism that runs `operation(report)` in a worker, receives its successful result, updates status, and restores controls when the worker finishes. Map these hooks to the target project's existing task mechanism.

## Startup integration

After loading saved settings and before populating the UI:

```python
if len(sys.argv) > 1:
    settings["folder_path"] = sys.argv[1]
```

## Acceptance checks

Verify all three registry commands, paths containing spaces, repeated installation, packaged and installed-source launchers, folder-field population, busy-state control disabling, and success status after completion.
