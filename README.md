# CLIBLASTER 🎵

CLIBLASTER is a personal, terminal-based music player and YouTube client featuring an interactive Terminal User Interface (TUI), playback controls, queue management, and YouTube library integration.

---

## Features

- 🎵 **Terminal User Interface (TUI)**: Polished split-panel interface displaying search results, active queue, and now-playing metadata.
- 🔎 **YouTube Search**: Search for tracks and artists directly within the terminal UI without leaving the app.
- 📜 **Queue Management**: Add search results or local files to an in-memory queue, skip tracks, and navigate playback history.
- ▶ **Playback Controls**: Play, pause, resume, stop, next, and previous track controls.
- 🔑 **Google/YouTube OAuth 2.0**: Secure authentication with Google to access personal YouTube library content.
- 📚 **Personal YouTube Library**: Browse your personal YouTube playlists and liked videos.
- ⌨ **Keyboard Controls**: Intuitive single-key shortcuts for instant playback control.

---

## Requirements

- **Python**: Python 3.9 or higher
- **OS**: Windows, macOS, or Linux
- **YouTube API**: Google Cloud OAuth 2.0 credentials (`client_secret.json`)

---

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/cliblaster.git
   cd cliblaster
   ```

2. **Create and activate a virtual environment**:

   - **Windows (PowerShell)**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```

   - **Linux / macOS**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install CLIBLASTER in editable mode**:
   ```bash
   pip install -e .
   ```

---

## Running CLIBLASTER

Once installed, simply launch CLIBLASTER from any terminal:

```bash
cliblaster
```

*(Alternative execution via python module: `python -m cliblaster`)*

---

## Configuration & YouTube API Setup

To use YouTube features, configure Google OAuth 2.0:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project and enable the **YouTube Data API v3**.
3. Go to **APIs & Services > Credentials** and click **Create Credentials > OAuth client ID**.
4. Choose **Desktop App**, download the JSON file, and rename it to `client_secret.json`.
5. Place `client_secret.json` in the root directory of CLIBLASTER (next to `pyproject.toml`).

> [!WARNING]
> **Security Notice**: Never commit `client_secret.json`, `token.json`, or `.env` files to Git. They are automatically ignored in `.gitignore`.

---

## Keyboard Controls (TUI)

| Key | Action |
| --- | --- |
| `Space` | Toggle Pause / Resume |
| `N` | Next track in queue |
| `B` | Previous track in queue |
| `S` | Focus Search input box |
| `A` | Add selected search result to queue |
| `↑` / `↓` | Navigate search results list |
| `Enter` | Submit search or select track |
| `Q` | Quit CLIBLASTER |

---

## Testing

Run the automated test suite with standard Python `unittest`:

```bash
python -m unittest discover tests
```
