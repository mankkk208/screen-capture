"""python3 -m screen_capture [--background | --settings | --quit | --install-shortcut |
                            --import-flameshot | --autostart on|off|status]"""
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

    if "--import-flameshot" in argv:
        from .config import DEFAULT_OWN_PATH
        from .settings_store import import_flameshot_token

        if import_flameshot_token():
            print(f"Copied the upload token from Flameshot's config into {DEFAULT_OWN_PATH}.")
        return 0

    if "--install-shortcut" in argv:
        from .keybinding import (
            DEFAULT_ACCEL, GSettingsStore, current_shortcut, ensure_shortcut, free_gnome_print, release_from_flameshot,
        )

        store = GSettingsStore()
        path = ensure_shortcut(store, current_shortcut(store) or DEFAULT_ACCEL)
        print(f"shortcut {current_shortcut(store)} -> {path}")
        if release_from_flameshot(store, current_shortcut(store)):
            print(f"{current_shortcut(store)} was taken from Flameshot's shortcut (its entry is kept, without a key).")
        if current_shortcut(store) == "Print" and free_gnome_print():
            print("Print now opens Screen Capture (GNOME's own screenshot UI was unbound from Print).")
        return 0

    from .app import CaptureApp

    return CaptureApp().run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
