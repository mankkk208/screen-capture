import configparser
import tempfile
import unittest
from pathlib import Path

from screen_capture.keybinding import (
    BINDING_NAME, current_shortcut, ensure_shortcut, find_conflict, find_ours, validate_accel,
)
from screen_capture.recent import RecentLinks
from screen_capture.settings_store import read_settings, save_settings, validate_endpoint
from screen_capture.tray_menu import MenuItem, build_layout

OUR_CMD = "gdbus call --session --dest io.avada.ScreenCapture --object-path /io/avada/ScreenCapture " \
          "--method org.freedesktop.Application.Activate {}"


class RecentLinksTest(unittest.TestCase):
    def test_keeps_newest_five_first(self):
        r = RecentLinks(5)
        for i in range(7):
            r.add(f"https://capture.avada.io/i/{i}")
        self.assertEqual(r.items(), [f"https://capture.avada.io/i/{i}" for i in (6, 5, 4, 3, 2)])

    def test_re_adding_moves_to_top_without_duplicate(self):
        r = RecentLinks(5)
        r.add("a")
        r.add("b")
        r.add("a")
        self.assertEqual(r.items(), ["a", "b"])


class SettingsStoreTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "screen-capture" / "config.ini"

    def test_save_then_read_roundtrip(self):
        save_settings(self.path, token="tok-1", upload_url="https://example.com/up")
        s = read_settings(self.path)
        self.assertEqual((s.token, s.upload_url), ("tok-1", "https://example.com/up"))

    def test_save_keeps_unrelated_keys(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[General]\nsave_dir = /tmp/x\n")
        save_settings(self.path, token="t", upload_url="https://e.com/u")
        p = configparser.ConfigParser(interpolation=None)
        p.read(self.path)
        self.assertEqual(p.get("General", "save_dir"), "/tmp/x")

    def test_empty_token_removes_own_token(self):
        save_settings(self.path, token="t", upload_url="https://e.com/u")
        save_settings(self.path, token="", upload_url="https://e.com/u")
        self.assertEqual(read_settings(self.path).token, "")

    def test_config_file_is_private(self):
        save_settings(self.path, token="t", upload_url="https://e.com/u")
        self.assertEqual(self.path.stat().st_mode & 0o077, 0)

    def test_validate_endpoint(self):
        self.assertIsNone(validate_endpoint("https://capture-api.avada.io/api/v1/upload"))
        self.assertIsNotNone(validate_endpoint("http://capture-api.avada.io/api/v1/upload"))
        self.assertIsNotNone(validate_endpoint("not a url"))
        self.assertIsNotNone(validate_endpoint(""))


class FakeStore:
    """In-memory stand-in for the GNOME keybinding gsettings."""

    def __init__(self, customs=None, others=None):
        self.customs = dict(customs or {})
        self.paths = list(self.customs)
        self.others = others or {}

    def custom_paths(self):
        return list(self.paths)

    def set_custom_paths(self, paths):
        self.paths = list(paths)

    def custom(self, path):
        return dict(self.customs.get(path, {"name": "", "command": "", "binding": ""}))

    def set_custom(self, path, **values):
        self.customs.setdefault(path, {"name": "", "command": "", "binding": ""}).update(values)

    def system_bindings(self):
        return self.others


BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"
FLAMESHOT = {"name": "lameshot", "command": "/usr/bin/flameshot gui", "binding": "Print"}


class KeybindingTest(unittest.TestCase):
    def test_validate_accel_requires_modifier(self):
        self.assertIsNone(validate_accel("<Control><Alt>s"))
        self.assertIsNotNone(validate_accel("s"))
        self.assertIsNotNone(validate_accel("<Shift>s"))
        self.assertIsNotNone(validate_accel("<Control>"))

    def test_find_ours_needs_name_and_app_id(self):
        store = FakeStore({BASE + "custom1/": FLAMESHOT,
                           BASE + "custom3/": {"name": BINDING_NAME, "command": "other", "binding": ""},
                           BASE + "custom0/": {"name": BINDING_NAME, "command": OUR_CMD, "binding": "<Control><Alt>s"}})
        self.assertEqual(find_ours(store), BASE + "custom0/")
        self.assertEqual(current_shortcut(store), "<Control><Alt>s")

    def test_ensure_shortcut_creates_next_free_slot_and_keeps_others(self):
        store = FakeStore({BASE + "custom1/": FLAMESHOT})
        path = ensure_shortcut(store, "<Control><Alt>s")
        self.assertEqual(path, BASE + "custom0/")
        self.assertEqual(store.custom(BASE + "custom1/"), FLAMESHOT)
        self.assertEqual(store.custom_paths(), [BASE + "custom1/", BASE + "custom0/"])

    def test_ensure_shortcut_updates_existing_entry(self):
        store = FakeStore({BASE + "custom0/": {"name": BINDING_NAME, "command": OUR_CMD, "binding": "<Control><Alt>s"}})
        ensure_shortcut(store, "<Super><Shift>s")
        self.assertEqual(len(store.custom_paths()), 1)
        self.assertEqual(current_shortcut(store), "<Super><Shift>s")

    def test_conflict_with_other_custom_binding(self):
        store = FakeStore({BASE + "custom1/": dict(FLAMESHOT, binding="<Control><Alt>p")})
        self.assertIn("lameshot", find_conflict(store, "<Alt><Control>P"))

    def test_conflict_with_system_binding(self):
        store = FakeStore(others={"Lock screen": ["<Super>l"]})
        self.assertEqual(find_conflict(store, "<Super>l"), "Lock screen")

    def test_own_binding_is_not_a_conflict(self):
        store = FakeStore({BASE + "custom0/": {"name": BINDING_NAME, "command": OUR_CMD, "binding": "<Control><Alt>s"}})
        self.assertIsNone(find_conflict(store, "<Control><Alt>s"))


class TrayMenuTest(unittest.TestCase):
    def test_layout_shape_for_dbusmenu(self):
        items = [MenuItem(1, "Capture"), MenuItem(2, "", separator=True),
                 MenuItem(3, "Recent links", children=[MenuItem(4, "https://x/1")])]
        layout = build_layout(items)
        self.assertEqual(layout.get_type_string(), "(ia{sv}av)")
        root_id, root_props, children = layout.unpack()
        self.assertEqual(root_id, 0)
        self.assertEqual(root_props["children-display"], "submenu")
        self.assertEqual(len(children), 3)
        self.assertEqual(children[1][1]["type"], "separator")
        self.assertEqual(children[2][2][0][1]["label"], "https://x/1")

    def test_disabled_item(self):
        layout = build_layout([MenuItem(5, "No links yet", enabled=False)])
        self.assertFalse(layout.unpack()[2][0][1]["enabled"])


class TrayNodeTest(unittest.TestCase):
    def test_build_node_returns_submenu_subtree(self):
        from screen_capture.tray_menu import build_node

        sub = MenuItem(3, "Recent links", children=[MenuItem(100, "https://x/1"), MenuItem(101, "https://x/2")])
        item_id, props, children = build_node(sub).unpack()
        self.assertEqual(item_id, 3)
        self.assertEqual(props["children-display"], "submenu")
        self.assertEqual([c[0] for c in children], [100, 101])

    def test_item_props_are_variants_and_escape_mnemonics(self):
        from screen_capture.tray_menu import item_props

        props = item_props(MenuItem(7, "https://x/a_b"))
        self.assertEqual(props["label"].unpack(), "https://x/a__b")
        self.assertTrue(props["enabled"].unpack())
