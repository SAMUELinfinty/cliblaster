"""
Terminal User Interface (TUI) for CLIBLASTER using Textual.
Cyberpunk hacker aesthetic: matrix rain + waveform, green-on-black.
"""

import math
import random
from typing import List, Optional, Dict

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static, Input, Button, Label
from textual.screen import Screen

from cliblaster.player import Player, PlayerState
from cliblaster.music_queue import Queue
from cliblaster.commands import CommandRouter
from cliblaster.auth import OAuthManager, AuthError
from cliblaster.track import Track


MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "0123456789ABCDEF<>{}[]|!@#$%^&*"
)


# ─────────────────────────────────────────────────────────────────────────────
# Matrix Rain  (top-left)
# ─────────────────────────────────────────────────────────────────────────────

class MatrixRainWidget(Static):
    """Animated matrix-rain falling characters, music-reactive speed."""

    BORDER_TITLE = "SIGNAL"

    def __init__(self, player: Player, **kwargs) -> None:
        super().__init__(**kwargs)
        self.player = player
        self._cols: List[Dict] = []
        self._ready = False

    def on_mount(self) -> None:
        self.set_interval(0.07, self._tick)

    def _setup(self, w: int, h: int) -> None:
        self._cols = []
        for c in range(w):
            self._cols.append({
                "x": c,
                "head": random.randint(-h, 0),
                "tail": random.randint(h // 4, max(h // 4 + 1, int(h * 0.85))),
                "speed": random.choice([1, 1, 1, 2]),
                "chars": [random.choice(MATRIX_CHARS) for _ in range(h + 5)],
            })
        self._ready = True

    def _tick(self) -> None:
        w = max(self.size.width - 2, 4)
        h = max(self.size.height - 2, 4)

        if not self._ready or len(self._cols) != w:
            self._setup(w, h)
            return

        if self.player.state == PlayerState.PLAYING:
            for col in self._cols:
                col["head"] += col["speed"]
                if random.random() < 0.15:
                    ri = random.randint(0, len(col["chars"]) - 1)
                    col["chars"][ri] = random.choice(MATRIX_CHARS)
                if col["head"] - col["tail"] > h:
                    col["head"] = random.randint(-h // 2, -2)
                    col["tail"] = random.randint(h // 4, max(h // 4 + 1, int(h * 0.85)))
                    col["speed"] = random.choice([1, 1, 2])
        elif self.player.state == PlayerState.PAUSED:
            for col in self._cols:
                if random.random() < 0.04:
                    ri = random.randint(0, len(col["chars"]) - 1)
                    col["chars"][ri] = random.choice(MATRIX_CHARS)

        self.refresh()

    def render(self) -> str:
        w = max(self.size.width - 2, 4)
        h = max(self.size.height - 2, 4)

        if not self._ready or len(self._cols) != w:
            return ""

        grid: List[List[str]] = [[""] * w for _ in range(h)]

        for col in self._cols:
            x = col["x"]
            if x >= w:
                continue
            head = col["head"]
            tail = col["tail"]
            chars = col["chars"]

            for row in range(h):
                char = chars[row % len(chars)]
                dist = head - row

                if row == head and 0 <= row < h:
                    grid[row][x] = f"[bold #ccffcc]{char}[/bold #ccffcc]"
                elif 0 < dist <= int(tail * 0.15):
                    grid[row][x] = f"[#00ff55]{char}[/#00ff55]"
                elif 0 < dist <= int(tail * 0.4):
                    grid[row][x] = f"[#00cc00]{char}[/#00cc00]"
                elif 0 < dist <= tail:
                    grid[row][x] = f"[#004400]{char}[/#004400]"
                else:
                    grid[row][x] = " "

        return "\n".join("".join(row) for row in grid)


# ─────────────────────────────────────────────────────────────────────────────
# Waveform Monitor  (top-right)
# ─────────────────────────────────────────────────────────────────────────────

class WaveformWidget(Static):
    """Dot-matrix waveform oscilloscope, music-reactive."""

    BORDER_TITLE = "WAVEFORM"

    def __init__(self, player: Player, **kwargs) -> None:
        super().__init__(**kwargs)
        self.player = player
        self._phase = 0.0
        self._buffer: List[float] = []

    def on_mount(self) -> None:
        self.set_interval(0.06, self._tick)

    def _tick(self) -> None:
        w = max(self.size.width - 2, 4)
        if len(self._buffer) != w:
            self._buffer = [0.0] * w

        if self.player.state == PlayerState.PLAYING:
            self._phase += 0.22
            amp = (
                math.sin(self._phase) * 0.5
                + math.sin(self._phase * 2.7 + 0.8) * 0.28
                + math.sin(self._phase * 0.5 + 2.1) * 0.15
                + random.gauss(0, 0.06)
            )
            amp = max(-1.0, min(1.0, amp))
        elif self.player.state == PlayerState.PAUSED:
            amp = random.gauss(0, 0.02)
        else:
            amp = 0.0

        self._buffer = self._buffer[1:] + [amp]
        self.refresh()

    def render(self) -> str:
        w = max(self.size.width - 2, 4)
        h = max(self.size.height - 2, 4)
        center = h // 2

        if len(self._buffer) != w:
            self._buffer = [0.0] * w

        grid = [[" "] * w for _ in range(h)]

        for col, amp in enumerate(self._buffer):
            span = int(abs(amp) * center * 0.95)
            top = max(0, center - span)
            bot = min(h - 1, center + span)
            for row in range(top, bot + 1):
                dist = abs(row - center)
                grid[row][col] = "┊" if (span > 0 and dist < span * 0.2) else "·"

        for col in range(w):
            if grid[center][col] == " " and col % 3 == 0:
                grid[center][col] = "·"

        lines = []
        for ri, row in enumerate(grid):
            dist = abs(ri - center)
            color = "#00ff55" if dist < 2 else ("#00cc00" if dist < center // 2 else "#007700")
            lines.append(f"[{color}]{''.join(row)}[/{color}]")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Oscilloscope strip  (bottom of right col)
# ─────────────────────────────────────────────────────────────────────────────

class OscilloscopeWidget(Static):
    """Thin horizontal waveform — like the chart in the reference image."""

    BORDER_TITLE = "OSCILLOSCOPE"

    def __init__(self, player: Player, **kwargs) -> None:
        super().__init__(**kwargs)
        self.player = player
        self._phase = 0.0
        self._history: List[float] = []

    def on_mount(self) -> None:
        self.set_interval(0.08, self._tick)

    def _tick(self) -> None:
        if self.player.state == PlayerState.PLAYING:
            self._phase += 0.28
            v = (
                math.sin(self._phase) * 0.55
                + math.sin(self._phase * 3.1) * 0.28
                + random.gauss(0, 0.08)
            )
        else:
            v = 0.0
        self._history.append(v)
        w = max(self.size.width - 2, 4)
        if len(self._history) > w:
            self._history = self._history[-w:]
        self.refresh()

    def render(self) -> str:
        w = max(self.size.width - 2, 4)
        h = max(self.size.height - 2, 2)
        center = h // 2

        buf = (
            [0.0] * (w - len(self._history)) + self._history
            if len(self._history) < w
            else self._history[-w:]
        )

        grid = [[" "] * w for _ in range(h)]
        for col, amp in enumerate(buf):
            row = center - int(amp * center * 0.9)
            row = max(0, min(h - 1, row))
            grid[row][col] = "▪"
            if row + 1 < h:
                grid[row + 1][col] = "·"

        lines = [f"[#00cc00]{''.join(row)}[/#00cc00]" for row in grid]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Info / Data fields  (bottom-right, top half)
# ─────────────────────────────────────────────────────────────────────────────

class InfoWidget(Static):
    """Cyberpunk data fields panel — TRACK, ARTIST, STATUS, VOL, QUEUE."""

    BORDER_TITLE = "DATA"

    def __init__(self, player: Player, queue: Queue, **kwargs) -> None:
        super().__init__(**kwargs)
        self.player = player
        self.queue = queue

    def render(self) -> str:
        track = self.queue.current()

        def trunc(s: str, n: int) -> str:
            return (s[:n - 2] + "..") if len(s) > n else s

        title  = trunc(track.title,  26) if track else "---"
        artist = trunc(track.artist, 26) if track else "---"

        if self.player.state == PlayerState.PLAYING:
            status, sc = "PLAYING",  "#00ff55"
        elif self.player.state == PlayerState.PAUSED:
            status, sc = "PAUSED",   "#aaaa00"
        else:
            status, sc = "STOPPED",  "#555555"

        vol     = self.player.volume
        bar     = "▓" * (vol // 10) + "░" * (10 - vol // 10)
        q_all   = self.queue.all()
        q_idx   = (self.queue.current_index + 1) if q_all else 0
        q_total = len(q_all)

        L = 16  # label column width

        def field(label: str, value: str, vc: str = "#00cc00") -> str:
            return f"[#005500]{label:<{L}}[/#005500][{vc}]{value}[/{vc}]"

        lines = [
            field("TRACK",  title),
            field("ARTIST", artist),
            field("STATUS", status, sc),
            f"[#005500]{'VOL':<{L}}[/#005500][#00cc00]{bar}  {vol}%[/#00cc00]",
            field("QUEUE",  f"{q_idx} / {q_total}"),
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Search Results  (bottom-left)
# ─────────────────────────────────────────────────────────────────────────────

class SearchResultsWidget(Static):
    """Search results list."""

    BORDER_TITLE = "RESULTS"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.tracks: List[Track] = []
        self.selected_index: int = 0

    def set_results(self, tracks: List[Track]) -> None:
        self.tracks = tracks
        self.selected_index = 0
        self.refresh()

    def get_selected(self) -> Optional[Track]:
        if 0 <= self.selected_index < len(self.tracks):
            return self.tracks[self.selected_index]
        return None

    def move_selection(self, delta: int) -> None:
        if self.tracks:
            self.selected_index = (self.selected_index + delta) % len(self.tracks)
            self.refresh()

    def render(self) -> str:
        if not self.tracks:
            return "[#004400]  press S to search[/#004400]"

        w = max(self.size.width - 4, 8)
        lines = []
        for i, t in enumerate(self.tracks[:14]):
            prefix = "> " if i == self.selected_index else "  "
            short  = (t.title[:w - 4] + "..") if len(t.title) > w - 2 else t.title
            if i == self.selected_index:
                lines.append(f"[bold #00ff55]{prefix}{short}[/bold #00ff55]")
            else:
                lines.append(f"[#007700]{prefix}{short}[/#007700]")
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Compatibility stubs (kept for legacy references)
# ─────────────────────────────────────────────────────────────────────────────

class NowPlayingWidget(Static):
    def __init__(self, player, queue, **kw):
        super().__init__(**kw); self.player = player; self.queue = queue
    def render(self): return ""

class QueueWidget(Static):
    def __init__(self, queue, **kw):
        super().__init__(**kw); self.queue = queue
    def render(self): return ""


# ─────────────────────────────────────────────────────────────────────────────
# Login screen
# ─────────────────────────────────────────────────────────────────────────────

class LoginScreen(Screen):
    BINDINGS = [
        Binding("enter", "submit_login", "Sign in", show=True),
        Binding("q",     "quit_app",     "Quit",    show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="login_outer"):
            with Vertical(id="login_box"):
                yield Static("▓▒░  C L I B L A S T E R  ░▒▓", id="login_title")
                yield Static("", id="login_gap")
                yield Static("AUTHENTICATION REQUIRED", id="login_sub")
                yield Static("", id="login_gap2")
                yield Button("[ SIGN IN WITH GOOGLE ]", id="btn_login")
                yield Label("", id="login_status")
        yield Footer()

    def on_mount(self) -> None:
        if not self.app.auth_manager.client_id:
            self._status("! client_secret.json not found")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_login":
            self.action_submit_login()

    def _status(self, text: str) -> None:
        self.query_one("#login_status", Label).update(text)

    def update_status(self, text: str) -> None:
        self._status(text)

    @work(thread=True)
    def action_submit_login(self) -> None:
        self.app.call_from_thread(self._status, "> opening browser...")
        try:
            self.app.auth_manager.login()
            self.app.call_from_thread(self._status, "> authenticated.")
            self.app.call_from_thread(lambda: self.app.push_screen(MainScreen()))
        except Exception as e:
            self.app.call_from_thread(self._status, f"! {e}")

    def action_quit_app(self) -> None:
        self.app.exit()


# ─────────────────────────────────────────────────────────────────────────────
# Main screen
# ─────────────────────────────────────────────────────────────────────────────

class MainScreen(Screen):
    BINDINGS = [
        Binding("space",      "toggle_pause",   "Play/Pause", show=True),
        Binding("equals",     "volume_up",       "Vol+",       show=True),
        Binding("minus",      "volume_down",     "Vol-",       show=True),
        Binding("plus",       "volume_up",       "Vol+",       show=False),
        Binding("underscore", "volume_down",     "Vol-",       show=False),
        Binding("n",          "next_track",      "Next",       show=True),
        Binding("b",          "previous_track",  "Prev",       show=True),
        Binding("s",          "focus_search",    "Search",     show=True),
        Binding("a",          "add_selected",    "Add",        show=True),
        Binding("l",          "logout_user",     "Logout",     show=True),
        Binding("up",         "move_up",         "Up",         show=False),
        Binding("down",       "move_down",       "Down",       show=False),
        Binding("q",          "quit_app",        "Quit",       show=True),
    ]

    def compose(self) -> ComposeResult:
        # ── top: matrix rain | waveform ─────────────────────────────────────
        with Horizontal(id="top_section"):
            yield MatrixRainWidget(player=self.app.player, id="matrix_rain")
            yield WaveformWidget(player=self.app.player, id="waveform")

        # ── bottom: results col | data col ──────────────────────────────────
        with Horizontal(id="bottom_section"):
            with Vertical(id="left_col"):
                yield SearchResultsWidget(id="search_results")
            with Vertical(id="right_col"):
                yield InfoWidget(
                    player=self.app.player,
                    queue=self.app.queue,
                    id="info_widget",
                )
                yield OscilloscopeWidget(player=self.app.player, id="oscilloscope")

        # ── search + status ─────────────────────────────────────────────────
        yield Input(placeholder="SEARCH YOUTUBE...", id="search_input")
        yield Label("", id="status_banner")
        yield Footer()

    # ── helpers ───────────────────────────────────────────────────────────────

    def set_status(self, msg: str) -> None:
        self.query_one("#status_banner", Label).update(msg)

    def refresh_ui(self) -> None:
        self.query_one("#info_widget", InfoWidget).refresh()

    # ── search ────────────────────────────────────────────────────────────────

    def action_focus_search(self) -> None:
        self.query_one("#search_input", Input).focus()

    @work(thread=True)
    def action_submit_search(self, query: str) -> None:
        self.app.call_from_thread(self.set_status, f"> searching: {query}...")
        try:
            self.app.router.dispatch(f"search {query}")
            results = self.app.router.recent_search_results

            def update() -> None:
                self.query_one("#search_results", SearchResultsWidget).set_results(results)
                self.set_status(
                    f"> {len(results)} results for '{query}'"
                    if results else "> no results"
                )

            self.app.call_from_thread(update)
        except Exception as e:
            self.app.call_from_thread(self.set_status, f"! {e}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        q = event.value.strip()
        if q:
            self.action_submit_search(q)
            self.set_focus(None)

    # ── navigation ────────────────────────────────────────────────────────────

    def action_move_up(self) -> None:
        self.query_one("#search_results", SearchResultsWidget).move_selection(-1)

    def action_move_down(self) -> None:
        self.query_one("#search_results", SearchResultsWidget).move_selection(1)

    # ── playback ──────────────────────────────────────────────────────────────

    def action_add_selected(self) -> None:
        track = self.query_one("#search_results", SearchResultsWidget).get_selected()
        if track:
            app = getattr(self, "_app", None) or self.app
            app.queue.add(track)
            self.set_status(f"> added: {track.title}")
            self.refresh_ui()
            if app.player.state == PlayerState.STOPPED:
                self._play_current()
        else:
            self.set_status("> no result selected")

    @work(thread=True)
    def _play_current(self) -> None:
        app = getattr(self, "_app", None) or self.app
        track = app.queue.current()
        if not track:
            return
        is_yt = "youtube.com/watch" in track.source or "youtu.be/" in track.source
        if is_yt:
            self.app.call_from_thread(
                self.set_status, f"> downloading: {track.title}..."
            )
        try:
            app.player.play()
            self.app.call_from_thread(self.set_status, f"> playing: {track.title}")
        except Exception as e:
            self.app.call_from_thread(self.set_status, f"! {e}")
        self.app.call_from_thread(self.refresh_ui)

    def action_toggle_pause(self) -> None:
        if not self.app.queue.current():
            self.set_status("> queue empty")
            return
        if self.app.player.state == PlayerState.PLAYING:
            self.app.player.pause()
            self.set_status("> paused")
            self.refresh_ui()
        elif self.app.player.state == PlayerState.PAUSED:
            self.app.player.resume()
            self.set_status("> playing")
            self.refresh_ui()
        else:
            self._play_current()

    def action_next_track(self) -> None:
        if self.app.queue.next():
            self._play_current()
        else:
            self.set_status("> end of queue")
        self.refresh_ui()

    def action_previous_track(self) -> None:
        if self.app.queue.previous():
            self._play_current()
        else:
            self.set_status("> start of queue")
        self.refresh_ui()

    def action_volume_up(self) -> None:
        app = getattr(self, "_app", None) or self.app
        self.set_status(f"> vol: {app.player.volume_up(10)}%")
        self.refresh_ui()

    def action_volume_down(self) -> None:
        app = getattr(self, "_app", None) or self.app
        self.set_status(f"> vol: {app.player.volume_down(10)}%")
        self.refresh_ui()

    def action_logout_user(self) -> None:
        self.app.auth_manager.logout()
        self.app.push_screen(LoginScreen())

    def action_quit_app(self) -> None:
        self.app.exit()


# ─────────────────────────────────────────────────────────────────────────────
# Application
# ─────────────────────────────────────────────────────────────────────────────

class CLIBLASTERApp(App):
    """CLIBLASTER — cyberpunk terminal music player."""

    CSS = """
    /* ─── Global ─────────────────────────────────────────────────────────── */
    Screen {
        background: #000000;
        color: #00cc00;
    }

    /* ─── Top section ─────────────────────────────────────────────────────── */
    #top_section {
        height: 2fr;
    }

    MatrixRainWidget {
        width: 1fr;
        height: 100%;
        border: solid #004400;
    }

    WaveformWidget {
        width: 1fr;
        height: 100%;
        border: solid #004400;
    }

    /* ─── Bottom section ──────────────────────────────────────────────────── */
    #bottom_section {
        height: 1fr;
    }

    #left_col {
        width: 30;
        height: 100%;
    }

    #right_col {
        width: 1fr;
        height: 100%;
    }

    SearchResultsWidget {
        height: 1fr;
        border: solid #004400;
        padding: 0 1;
    }

    InfoWidget {
        height: 1fr;
        border: solid #004400;
        padding: 0 1;
    }

    OscilloscopeWidget {
        height: 7;
        border: solid #004400;
    }

    /* ─── Search + status ─────────────────────────────────────────────────── */
    #search_input {
        height: 3;
        border: solid #004400;
        background: #000000;
        color: #00cc00;
    }

    Input:focus {
        border: solid #00cc00;
    }

    #status_banner {
        height: 1;
        color: #008800;
        background: #000000;
        padding: 0 1;
    }

    /* ─── Footer ──────────────────────────────────────────────────────────── */
    Footer {
        background: #001100;
        color: #008800;
    }

    FooterKey {
        background: #001100;
        color: #008800;
    }

    FooterKey:hover {
        background: #003300;
        color: #00ff55;
    }

    /* ─── Login ───────────────────────────────────────────────────────────── */
    #login_outer {
        align: center middle;
        height: 1fr;
    }

    #login_box {
        width: 36;
        height: auto;
        border: solid #00aa00;
        background: #000000;
        padding: 1 2;
        align: center middle;
    }

    #login_title {
        color: #00ff55;
        text-style: bold;
        content-align: center middle;
        width: 1fr;
    }

    #login_sub {
        color: #008800;
        content-align: center middle;
        width: 1fr;
    }

    #login_gap, #login_gap2 {
        height: 1;
    }

    Button {
        background: #001100;
        color: #00cc00;
        border: tall #004400;
        width: 1fr;
    }

    Button:hover {
        background: #003300;
        color: #00ff55;
    }

    Button:focus {
        background: #002200;
        color: #00ff55;
        border: tall #00cc00;
    }

    #login_status {
        color: #00aa00;
        content-align: center middle;
        width: 1fr;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        router: CommandRouter,
        player: Player,
        queue: Queue,
        auth_manager: OAuthManager,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.router = router
        self.player = player
        self.queue = queue
        self.auth_manager = auth_manager

    def on_mount(self) -> None:
        if self.auth_manager.is_authenticated():
            self.push_screen(MainScreen())
        else:
            self.push_screen(LoginScreen())

    def action_quit_app(self) -> None:
        self.exit()
