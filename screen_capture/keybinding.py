"""The GNOME custom keybinding that triggers a capture. Only our own entry is ever modified."""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, Gtk  # noqa: E402

APP_ID = "io.avada.ScreenCapture"
BINDING_NAME = "Screen Capture"
TRIGGER = (f"gdbus call --session --dest {APP_ID} --object-path /io/avada/ScreenCapture "
           "--method org.freedesktop.Application.Activate {}")
DEFAULT_ACCEL = "Print"

MEDIA_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys.custom-keybinding"
BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
SYSTEM_SCHEMAS = ("org.gnome.desktop.wm.keybindings", "org.gnome.shell.keybindings", MEDIA_KEYS,
                  "org.gnome.mutter.keybindings", "org.gnome.mutter.wayland.keybindings")
REQUIRED_MODS = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK


def _parse(accel: str):
    ok, key, mods = Gtk.accelerator_parse(accel)
    return (Gdk.keyval_to_lower(key), int(mods)) if ok and key else None


def validate_accel(accel: str) -> str | None:
    ok, key, mods = Gtk.accelerator_parse(accel)
    if not ok or not key:
        return "Not a valid shortcut"
    # Keys that type text (letters, digits, space…) need Ctrl/Alt/Super; keys like Print or F9 don't.
    types_text = Gdk.keyval_to_unicode(key) != 0
    if types_text and not mods & REQUIRED_MODS:
        return "Use at least one of Ctrl, Alt or Super"
    return None


def label(accel: str) -> str:
    ok, key, mods = Gtk.accelerator_parse(accel)
    return Gtk.accelerator_get_label(key, mods) if ok else accel


def find_ours(store) -> str | None:
    for path in store.custom_paths():
        c = store.custom(path)
        if c["name"] == BINDING_NAME and APP_ID in c["command"]:
            return path
    return None


def current_shortcut(store) -> str | None:
    path = find_ours(store)
    return store.custom(path)["binding"] if path else None


def ensure_shortcut(store, accel: str) -> str:
    """Create or update our entry; append a new customN path only when we have none."""
    path = find_ours(store)
    if path is None:
        paths = store.custom_paths()
        n = 0
        while f"{BASE}custom{n}/" in paths:
            n += 1
        path = f"{BASE}custom{n}/"
        store.set_custom_paths(paths + [path])
    store.set_custom(path, name=BINDING_NAME, command=TRIGGER, binding=accel)
    return path


def find_conflict(store, accel: str) -> str | None:
    """Name of whatever else already uses this shortcut, or None."""
    want = _parse(accel)
    if want is None:
        return None
    ours = find_ours(store)
    for path in store.custom_paths():
        if path == ours:
            continue
        c = store.custom(path)
        if c["binding"] and _parse(c["binding"]) == want:
            return c["name"] or "another custom shortcut"
    for name, accels in store.system_bindings().items():
        if any(a and _parse(a) == want for a in accels):
            return name
    return None


def free_gnome_print() -> bool:
    """GNOME binds Print to its screenshot UI; unbind it there when Print is ours. Returns True if changed."""
    shell = Gio.Settings.new("org.gnome.shell.keybindings")
    current = list(shell.get_strv("show-screenshot-ui"))
    if "Print" not in current:
        return False
    shell.set_strv("show-screenshot-ui", [a for a in current if a != "Print"])
    Gio.Settings.sync()
    return True


class GSettingsStore:
    """Real store backed by Gio.Settings."""

    def __init__(self):
        self._media = Gio.Settings.new(MEDIA_KEYS)

    def custom_paths(self):
        return list(self._media.get_strv("custom-keybindings"))

    def set_custom_paths(self, paths):
        self._media.set_strv("custom-keybindings", paths)

    def _item(self, path):
        return Gio.Settings.new_with_path(CUSTOM_SCHEMA, path)

    def custom(self, path):
        s = self._item(path)
        return {k: s.get_string(k) for k in ("name", "command", "binding")}

    def set_custom(self, path, **values):
        s = self._item(path)
        for k, v in values.items():
            s.set_string(k, v)
        Gio.Settings.sync()

    def system_bindings(self):
        out = {}
        source = Gio.SettingsSchemaSource.get_default()
        for schema_id in SYSTEM_SCHEMAS:
            schema = source.lookup(schema_id, True)
            if schema is None:
                continue
            settings = Gio.Settings.new(schema_id)
            for key in schema.list_keys():
                kind = schema.get_key(key).get_value_type().dup_string()
                if kind == "as":
                    out[f"{key} ({schema_id.split('.')[-1]})"] = list(settings.get_strv(key))
                elif kind == "s" and key not in ("custom-keybindings",):
                    out[f"{key} ({schema_id.split('.')[-1]})"] = [settings.get_string(key)]
        return out
