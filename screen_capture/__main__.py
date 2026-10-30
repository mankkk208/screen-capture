"""python3 -m screen_capture [--background | --quit | --autostart on|off|status]"""
import sys


def main(argv: list[str]) -> int:
    if "--autostart" in argv:
        from .autostart import is_autostart_enabled, set_autostart

        i = argv.index("--autostart")
        choice = argv[i + 1] if i + 1 < len(argv) else "status"
        if choice in ("on", "off"):
            path = set_autostart(choice == "on")
            print(f"launch on startup: {choice}" + (f" ({path})" if path else ""))
        elif choice == "status":
            print("launch on startup: " + ("on" if is_autostart_enabled() else "off"))
        else:
            print("usage: --autostart on|off|status", file=sys.stderr)
            return 2
        return 0

    from .app import CaptureApp

    return CaptureApp().run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
