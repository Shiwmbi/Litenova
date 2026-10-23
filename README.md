# Litenova

Litenova 3.0.1 is a Windows desktop reader for EPUB light novels and CBZ manga/manhwa, built with Python and PySide6.

## Features

- Import EPUB and CBZ files into a local Library with covers and metadata.
- Search and organize books, including custom categories.
- Read EPUB chapters with a table of contents and reader settings.
- Read CBZ manga and manhwa with the comic reader.
- Save reading progress and resume from Library or History.
- Use the dark appearance and persistent reading preferences.
- Open EPUB/CBZ files from Windows Explorer or the command line.
- First-launch onboarding and a configurable start page.

Books are supplied by the user. Reading and Library management work locally without an account or cloud service.

## Windows installation

Download **Litenova-Setup-3.0.1.exe** from this repository's GitHub Releases and run it. Python is not required for the installed application. The build targets 64-bit Windows 10/11.

Installation is per-user, normally under:

```text
%LOCALAPPDATA%\Programs\Litenova
```

Launch Litenova from the Start Menu. A Desktop shortcut is optional. In Browse, select EPUB/CBZ files and import them, then open a book from Library. CBZ imports use the Manga or Manhwa category.

To upgrade an existing installation, run the new installer directly over it. Uninstalling removes the program and Litenova's file-handler registration, while preserving personal Library data. Reinstalling restores access to that data.

### Open files from Windows

Use **Open with > Litenova** for `.epub` and `.cbz` files. To use double-click opening, choose Litenova as the default application for each format in Windows. The installer registers Litenova as an available handler without forcing a default-app change.

Command-line examples in PowerShell:

```powershell
& "$env:LOCALAPPDATA\Programs\Litenova\Litenova.exe" "C:\My Books\Novel.epub"
& "$env:LOCALAPPDATA\Programs\Litenova\Litenova.exe" "C:\My Comics\Chapter 01.cbz"
```

A valid file is processed after the main window and any first-launch onboarding are ready. New books use the existing import service; matching imported books are opened without another import. Unsupported formats, directories, and missing paths are ignored.

## Local data

The installed application stores books, covers, and its SQLite database under:

```text
%LOCALAPPDATA%\Litenova
```

Source-mode development uses `data/` inside the project instead. Book metadata, progress, history, and categories are stored locally. Preferences also use Qt QSettings; not all settings are stored in SQLite. Neither data nor QSettings should be reset when upgrading or uninstalling.

Private books, covers, databases, and generated build output must not be committed or included in release downloads.

## Development

Use a Python version compatible with `requirements.txt`. The current release build uses Python 3.14 and the project's `.venv`.

From a local checkout in PowerShell:

```powershell
cd C:\Projects\Litenova
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

To launch with a file in source mode:

```powershell
python main.py "C:\My Books\Novel.epub"
```

The main components are PySide6 for the UI, EbookLib for EPUB processing, Pillow and ZIP-based services for comics, SQLite for the Library, PyInstaller for packaging, and Inno Setup for the Windows installer.

## Release build

Validate Python source and use the existing build script:

```powershell
python -m compileall -q main.py app
.\release_v3.ps1
```

The script uses `.venv\Scripts\python.exe` and the tracked `Litenova.spec`, rebuilds generated `build/`, `dist/`, and `release/` output, checks for tracked private files without changing Git tracking, and writes:

```text
release\Litenova.exe
release\Litenova.exe.sha256.txt
```

Keep development files and personal data outside those generated output directories. Build the installer using the installed Inno Setup compiler; for a per-user Inno Setup 7 installation:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe" ".\installer\Litenova.iss"
```

Adjust the compiler path if Inno Setup is installed elsewhere. The installer script packages only `release\Litenova.exe` as the application payload.

Generate the installer checksum:

```powershell
$installer = ".\installer_output\Litenova-Setup-3.0.1.exe"
$hash = Get-FileHash -LiteralPath $installer -Algorithm SHA256
"$($hash.Hash)  Litenova-Setup-3.0.1.exe" | Set-Content -LiteralPath "$installer.sha256.txt" -Encoding Ascii
```

Upload these two generated files to the GitHub Release:

- `Litenova-Setup-3.0.1.exe`
- `Litenova-Setup-3.0.1.exe.sha256.txt`

The installer is the primary user download. The loose executable remains a build artifact. Release preparation does not commit, tag, push, or publish automatically. Code signing is a separate release task; a checksum verifies file contents but is not a signature.

## Scope and licensing

Supported book formats are EPUB and CBZ. Automatic updates, cloud synchronization, and online book downloads are not implemented.

This project was developed as an academic software project. Third-party libraries remain subject to their respective licenses.
