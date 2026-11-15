# XMD — Desktop application as shell for Windows CMD

**A Windows command-line environment with an integrated panel-based file manager and standalone companion application.**

![XMD](https://img.shields.io/badge/XMD-v2.0-blue?logo=windows-terminal)
![XMD Commander](https://img.shields.io/badge/XMD%20Commander-v2.0-0078D6?logo=files)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?logo=windows)
![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![Developer](https://img.shields.io/badge/Developer-Usersoft%20Inc.-black)

---

## About

**XMD (Xion Command)** is a desktop command-line application developed by **Usersoft Inc.** for Windows.

XMD provides a dedicated command-line environment with file system management, configurable interface settings, command execution, and built-in diagnostic tools.

The XMD ecosystem also includes **XMD COMMANDER** — a panel-based file manager integrated directly into the main XMD terminal while also being distributed as an independent desktop application.

Both applications can operate independently or together as part of the XMD environment.

## Components

### XMD — Main Application

The primary command-line environment of the XMD ecosystem.

**Features:**

- Dedicated command-line interface.
- File and directory management.
- File creation, reading, editing, copying, moving, and deletion.
- Directory navigation and file search.
- Configurable startup directory.
- Customizable fonts and color palettes.
- Adjustable window size and transparency.
- Multiple interface themes:
  - Default (XMD)
  - Standard (CMD)
  - Matrix
  - Hacker
- Configurable Windows code pages.
- Debug mode and diagnostic logging.
- Integrated XMD COMMANDER.

### XMD COMMANDER — File Manager

A panel-based file management application designed as a companion component of XMD.

XMD COMMANDER supports two operating modes:

**Integrated Mode**
- Launched directly from the XMD terminal.
- Shares the terminal's command environment.
- Synchronizes the current working directory in both directions.
- Allows returning to the terminal without closing the application.

**Standalone Mode**
- Runs independently from the main XMD terminal.
- Distributed as a separate application.
- Provides its own command interface and file management environment.

**Features:**

- Three-panel file management interface.
- Directory navigation and file selection.
- File and directory preview.
- Built-in text editor.
- File creation, deletion, moving, and renaming.
- Keyboard-driven navigation.
- Command-line interface.
- Python syntax highlighting.
- Preservation of file encoding and line endings.
- Protection against accidental loss of unsaved changes.

## System Requirements

| Component | Requirement |
|---|---|
| Operating System | Windows 10 / Windows 11 |
| Architecture | x64 |
| Minimum Resolution | 1024 × 576 |
| Administrator Privileges | Not required |
| Python | Required only for source execution |

## Installation

XMD and XMD COMMANDER are distributed as independent applications.

| Application | Installer |
|---|---|
| XMD | `XMD_Setup_v2.0.exe` |
| XMD COMMANDER | `XMD_Commander_Setup_v2.0.exe` |

Both applications can be installed independently.

The installation wizard provides an installation path, optional desktop shortcuts, and application launch options.

### Portable Mode

Both applications support portable execution without installation.

- `xmd.exe` — XMD terminal.
- `xmd_commander.exe` — XMD COMMANDER.

## Running from Source

To launch the main XMD application:

```bash
python xmd.py
```

To launch XMD COMMANDER independently:

```bash
python xmd_commander.py
```

## Command Interface

XMD provides commands for interacting with the file system and managing the working environment.

Some available commands:

| Command | Description |
|---|---|
| `help` | Display command reference |
| `xsh` | List directory contents |
| `xsh -l` | Display detailed directory listing |
| `cd` | Change working directory |
| `back` | Return to parent directory |
| `pwd` | Display current directory |
| `read` | Read file contents |
| `add /f` | Create a file |
| `add /d` | Create a directory |
| `add -copy` | Copy an item |
| `add -move` | Move an item |
| `add -ren` | Rename an item |
| `add -del` | Delete an item |
| `write -nw` | Create a file with text |
| `write -ow` | Overwrite file contents |
| `setting` | Open terminal settings |
| `xmd` | Launch XMD COMMANDER |
| `ver` | Display product version |
| `about` | Display application information |
| `exit` | Close XMD |

## Project Structure

The XMD ecosystem consists of two independently executable applications:

```text
XMD
│
├── XMD
│   ├── Command Environment
│   ├── File System Operations
│   ├── Settings
│   ├── Diagnostics
│   └── Integrated XMD COMMANDER
│
└── XMD COMMANDER
    ├── Panel-Based File Manager
    ├── Directory Navigation
    ├── File Preview
    ├── Text Editor
    ├── Command Interface
    └── Standalone Application
```

## Documentation

The project includes documentation covering:

- Installation and application startup.
- Terminal interface and configuration.
- Command reference.
- XMD COMMANDER interface and operation.
- Keyboard shortcuts.
- File editing and saving.
- Diagnostics and troubleshooting.

## Development

> **Developer:** Usersoft Inc.  
> **Product:** XMD  
> **General Application:** XMD  
> **Companion Application:** XMD COMMANDER  
> **XMD Version:** 2.0  
> **XMD COMMANDER Version:** 2.0  
> **Release Year:** 2026

XMD is part of the **XSystem** software ecosystem.

---

© 2026 Usersoft Inc.
