import sys
import os
from cliblaster.commands import CommandRouter
from cliblaster.player import Player
from cliblaster.audio_backend_pygame import PygameBackend
from cliblaster.music_queue import Queue


def load_env() -> None:
    """Simple parser to load a .env file without adding the python-dotenv dependency."""
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

def setup_encoding() -> None:
    """Ensure standard output and error stream encodings support UTF-8 (especially on Windows)."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> None:
    load_env()
    setup_encoding()

    from cliblaster.auth import OAuthManager
    auth_manager = OAuthManager()
    backend = PygameBackend()
    queue = Queue()
    player = Player(backend=backend, queue=queue)
    router = CommandRouter(player=player, queue=queue, auth_manager=auth_manager)

    if "--cli" in sys.argv:
        print("CLIBLASTER 🎵\n")
        if auth_manager.is_authenticated():
            print("✓ Authentication available")
            print("✓ Welcome back\n")
        else:
            print("YouTube account not connected.")
            print("Run 'login' to connect.\n")

        while True:
            try:
                raw_input = input(">>>>* ")
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                sys.exit(0)

            result = router.dispatch(raw_input)
            if result.should_quit:
                break
    else:
        try:
            from cliblaster.tui import CLIBLASTERApp
            app = CLIBLASTERApp(router=router, player=player, queue=queue, auth_manager=auth_manager)
            app.run()
        except Exception as e:
            print(f"TUI failed to initialize ({e}). Falling back to CLI mode.\n")
            print("CLIBLASTER 🎵\n")
            if not auth_manager.is_authenticated():
                print("YouTube account not connected. Run 'login' to connect.\n")
            while True:
                try:
                    raw_input = input(">>>>* ")
                except (KeyboardInterrupt, EOFError):
                    print("\nGoodbye!")
                    sys.exit(0)

                result = router.dispatch(raw_input)
                if result.should_quit:
                    break


if __name__ == "__main__":
    main()
