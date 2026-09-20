# Litenova

**Litenova** is a desktop-based EPUB light novel reader and personal library management application.

It allows users to import their own EPUB light novels, organize them in a local library, read them directly inside the application, customize their reading experience, and automatically save their reading progress.

---

## Features

### EPUB Library Management

- Import EPUB files from the computer
- Store imported EPUBs locally
- Display book title
- Display author
- Display book cover
- Search books by title
- Search books by author
- Remove books from the library
- Prevent duplicate EPUB imports

### EPUB Reader

- Read EPUB light novels directly inside Litenova
- Previous chapter navigation
- Next chapter navigation
- Table of Contents
- Jump directly to a chapter
- Scroll through chapter content

### Reading Progress

- Automatically save the current chapter
- Automatically save scroll position
- Resume reading from the previous position
- Progress remains saved after restarting the application

### Reading Preferences

- Increase reader font size
- Decrease reader font size
- Dark mode
- Light mode
- Settings are automatically saved

### Offline Storage

Litenova works locally without requiring:

- User accounts
- Cloud storage
- Internet connection
- Online ebook services

Book information, settings, and reading progress are stored locally using SQLite.

---

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Desktop GUI | PySide6 |
| EPUB Processing | EbookLib |
| Database | SQLite |
| Packaging | PyInstaller |
| Version Control | Git / GitHub |
| Project Management | Trello |
| UI Design | Figma |

---

## System Requirements

### Development

- Windows 10 or Windows 11
- Python 3
- pip
- Git

### Packaged Application

The packaged Windows version does not require Python to be installed.

---

## Installation for Users

### Windows Executable

1. Download `Litenova.exe`.
2. Open `Litenova.exe`.
3. Open the **Browse** page.
4. Select an `.epub` file.
5. Click **Import EPUB**.
6. Open the imported book from the **Library**.

---

## Development Setup

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/Litenova.git
```

Enter the project directory:

```bash
cd Litenova
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run Litenova:

```bash
python main.py
```

---

## Project Structure

```text
Litenova/
│
├── main.py
├── requirements.txt
├── version_info.txt
├── README.md
│
├── app/
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   └── books_repository.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── book.py
│   │   └── reading_progress.py
│   │
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── library_page.py
│   │   ├── browse_page.py
│   │   ├── reader_page.py
│   │   └── settings_page.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── epub_service.py
│   │   ├── import_service.py
│   │   ├── library_service.py
│   │   ├── path_service.py
│   │   ├── progress_service.py
│   │   ├── settings_service.py
│   │   └── theme_service.py
│   │
│   ├── styles/
│   │   ├── dark.qss
│   │   └── light.qss
│   │
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── book_card.py
│   │   ├── dialogs.py
│   │   ├── search_bar.py
│   │   └── sidebar.py
│   │
│   └── windows/
│       ├── __init__.py
│       └── main_window.py
│
├── data/
│   ├── books/
│   └── covers/
│
└── resources/
    └── icons/
        └── litenova.ico
```

---

## Application Workflow

```text
Launch Litenova
      ↓
Library
      ↓
Browse
      ↓
Choose EPUB
      ↓
Import EPUB
      ↓
EbookLib reads metadata
      ↓
EPUB copied to local storage
      ↓
Book saved in SQLite
      ↓
Book appears in Library
      ↓
Click Book
      ↓
Reader
      ↓
Read / Navigate Chapters
      ↓
Progress Automatically Saved
```

---

## Local Data Storage

During development, application data is stored under:

```text
Litenova/data/
```

The packaged Windows application stores user data under:

```text
%LOCALAPPDATA%\Litenova
```

This includes:

```text
Litenova/
├── litenova.db
├── books/
└── covers/
```

### `litenova.db`

The SQLite database stores:

- Book information
- EPUB paths
- Cover paths
- Reading progress
- Reader preferences

---

## Database

Litenova uses three main SQLite tables.

### Books

Stores imported EPUB information.

```text
books
├── id
├── title
├── author
├── epub_path
├── cover_path
└── date_added
```

### Reading Progress

Stores the user's most recent reading position.

```text
reading_progress
├── id
├── book_id
├── chapter_index
├── position
└── last_read
```

### Settings

Stores persistent application preferences.

```text
settings
├── key
└── value
```

---

## Reader Navigation

Books are opened directly from the Library.

The Reader is intentionally not displayed as a main sidebar page.

```text
Library
   ↓
Click Book
   ↓
Reader
```

Reader navigation includes:

```text
← Back to Library

☰ Contents

← Previous     Chapter Information     Next →
```

---

## Reading Progress

Litenova automatically records:

```text
Book
   +
Current Chapter
   +
Scroll Position
```

When the book is opened again:

```text
Open Book
   ↓
Load Progress from SQLite
   ↓
Restore Chapter
   ↓
Restore Scroll Position
```

---

## Supported Format

Litenova currently supports:

```text
EPUB
```

---

## Out of Scope

The current version does not include:

- PDF support
- MOBI support
- AZW3 support
- DRM-protected EPUB support
- Online ebook downloads
- Ebook purchasing
- Cloud synchronization
- Cloud backup
- User accounts
- Audiobooks
- Text-to-speech
- Advanced highlighting
- Advanced annotations
- Online dictionary integration

---

## Building the Windows Executable

Install PyInstaller:

```bash
pip install pyinstaller
```

Build Litenova:

```powershell
pyinstaller --noconfirm --clean --onefile --windowed --name Litenova --icon "resources\icons\litenova.ico" --version-file version_info.txt --add-data "app\styles;app\styles" --add-data "resources\icons\litenova.ico;resources\icons" main.py
```

The resulting executable will be located at:

```text
dist\Litenova.exe
```

---

## Version

Current version:

```text
1.0.0
```

---

## License

This project was developed as an academic software project.

Third-party libraries used by the application remain subject to their respective licenses.

---

## Author

Developed as part of the **Litenova: A Desktop-Based EPUB Light Novel Reader and Personal Library Management System** project.