"""Settings window: token, endpoint, capture shortcut, launch on login. Nothing applies until Save."""
import configparser

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from . import autostart  # noqa: E402
from .config import DEFAULT_FLAMESHOT_PATH, DEFAULT_OWN_PATH  # noqa: E402
from .keybinding import (  # noqa: E402
    DEFAULT_ACCEL, GSettingsStore, current_shortcut, ensure_shortcut, find_conflict, label, validate_accel,
)
from .settings_store import read_settings, save_settings, validate_endpoint  # noqa: E402

_adw_ready = False


def _flameshot_has_token() -> bool:
    p = configparser.ConfigParser(interpolation=None)
    p.optionxform = str
    try:
        p.read(DEFAULT_FLAMESHOT_PATH, encoding="utf-8")
    except (configparser.Error, OSError, UnicodeDecodeError):
        return False
    return bool(p.get("General", "customUploadToken", fallback="").strip())


class SettingsWindow(Adw.Window):
    def __init__(self, app: Gtk.Application, on_saved):
        global _adw_ready
        if not _adw_ready:
            Adw.init()
            _adw_ready = True
        super().__init__(application=app, title="Screen Capture Settings", modal=False)
        self.set_default_size(560, -1)
        self.on_saved = on_saved
        self.store = GSettingsStore()
        settings = read_settings(DEFAULT_OWN_PATH)
        self.initial = {
            "token": settings.token,
            "endpoint": settings.upload_url,
            "accel": current_shortcut(self.store) or DEFAULT_ACCEL,
            "autostart": autostart.is_autostart_enabled(),
        }
        self.accel = self.initial["accel"]
        self.recording = False

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_a: self.close())
        header.pack_start(cancel)
        self.save_button = Gtk.Button(label="Save")
        self.save_button.add_css_class("suggested-action")
        self.save_button.connect("clicked", self._save)
        header.pack_end(self.save_button)
        view.add_top_bar(header)

        page = Adw.PreferencesPage()
        upload = Adw.PreferencesGroup(title="Upload")
        if not settings.token and _flameshot_has_token():
            upload.set_description("Token field is empty: using the token from Flameshot's config. "
                                   "Enter a token here to use it instead.")
        self.token_row = Adw.PasswordEntryRow(title="Upload token")
        self.token_row.set_text(settings.token)
        self.token_row.connect("changed", self._validate)
        upload.add(self.token_row)
        self.endpoint_row = Adw.EntryRow(title="Upload endpoint")
        self.endpoint_row.set_text(settings.upload_url)
        self.endpoint_row.connect("changed", self._validate)
        upload.add(self.endpoint_row)
        page.add(upload)

        capture = Adw.PreferencesGroup(title="Capture")
        self.shortcut_row = Adw.ActionRow(title="Capture shortcut")
        self.shortcut_button = Gtk.Button(label=label(self.accel), valign=Gtk.Align.CENTER)
        self.shortcut_button.connect("clicked", self._start_recording)
        self.shortcut_row.add_suffix(self.shortcut_button)
        self.shortcut_row.set_activatable_widget(self.shortcut_button)
        capture.add(self.shortcut_row)
        self.autostart_row = Adw.SwitchRow(title="Launch on login",
                                           subtitle="Start in the background so the first capture is instant")
        self.autostart_row.set_active(self.initial["autostart"])
        self.autostart_row.connect("notify::active", self._validate)
        capture.add(self.autostart_row)
        page.add(capture)

        self.toasts = Adw.ToastOverlay(child=page)
        view.set_content(self.toasts)
        self.set_content(view)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)
        self._validate()

    # ---- shortcut recording ------------------------------------------------------

    def _start_recording(self, *_a):
        self.recording = True
        self.shortcut_button.set_label("Press new shortcut… (Esc to cancel)")
        self.shortcut_row.set_subtitle("")

    def _key(self, _c, keyval, _code, state):
        if not self.recording:
            if keyval == Gdk.KEY_Escape:
                self.close()
                return True
            return False
        if keyval == Gdk.KEY_Escape:
            self.recording = False
            self.shortcut_button.set_label(label(self.accel))
            return True
        if Gdk.keyval_name(keyval) in ("Control_L", "Control_R", "Alt_L", "Alt_R", "Shift_L", "Shift_R",
                                       "Super_L", "Super_R", "Meta_L", "Meta_R", "ISO_Level3_Shift"):
            return True  # wait for the real key
        mods = state & Gtk.accelerator_get_default_mod_mask()
        self.accel = Gtk.accelerator_name(Gdk.keyval_to_lower(keyval), mods)
        self.recording = False
        self.shortcut_button.set_label(label(self.accel))
        self._validate()
        return True

    # ---- validation and save -----------------------------------------------------------

    def _current(self) -> dict:
        return {"token": self.token_row.get_text().strip(), "endpoint": self.endpoint_row.get_text().strip(),
                "accel": self.accel, "autostart": self.autostart_row.get_active()}

    def _errors(self) -> dict:
        cur = self._current()
        errors = {}
        if msg := validate_endpoint(cur["endpoint"]):
            errors["endpoint"] = msg
        if msg := validate_accel(cur["accel"]):
            errors["accel"] = msg
        elif cur["accel"] != self.initial["accel"] and (other := find_conflict(self.store, cur["accel"])):
            errors["accel"] = f"Already used by “{other}”"
        return errors

    def _validate(self, *_a):
        errors = self._errors()
        for key, row in (("endpoint", self.endpoint_row),):
            if key in errors:
                row.add_css_class("error")
                row.set_tooltip_text(errors[key])
            else:
                row.remove_css_class("error")
                row.set_tooltip_text(None)
        self.shortcut_row.set_subtitle(errors.get("accel", ""))
        if "accel" in errors:
            self.shortcut_row.add_css_class("error")
        else:
            self.shortcut_row.remove_css_class("error")
        if "endpoint" in errors:
            self.endpoint_row.set_title(f"Upload endpoint — {errors['endpoint']}")
        else:
            self.endpoint_row.set_title("Upload endpoint")
        self.save_button.set_sensitive(not errors and self._current() != self.initial)

    def _save(self, *_a):
        if self._errors():
            return
        cur = self._current()
        try:
            save_settings(DEFAULT_OWN_PATH, token=cur["token"], upload_url=cur["endpoint"])
            if cur["accel"] != self.initial["accel"]:
                ensure_shortcut(self.store, cur["accel"])
            if cur["autostart"] != self.initial["autostart"]:
                autostart.set_autostart(cur["autostart"])
        except OSError as e:
            self.toasts.add_toast(Adw.Toast(title=f"Could not save: {e.strerror or 'error'}"))
            return
        self.on_saved()
        self.close()
