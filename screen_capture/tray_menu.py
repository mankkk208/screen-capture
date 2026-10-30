"""Menu model → com.canonical.dbusmenu layout variant (pure, no D-Bus)."""
from dataclasses import dataclass, field

from gi.repository import GLib


@dataclass
class MenuItem:
    id: int
    label: str
    enabled: bool = True
    separator: bool = False
    children: list = field(default_factory=list)
    on_click: object = None


def item_props(item: MenuItem | None) -> dict:
    if item is None:
        return {"children-display": GLib.Variant("s", "submenu")}
    if item.separator:
        return {"type": GLib.Variant("s", "separator")}
    props = {"label": GLib.Variant("s", item.label.replace("_", "__")),  # "_" is a mnemonic marker
             "enabled": GLib.Variant("b", item.enabled)}
    if item.children:
        props["children-display"] = GLib.Variant("s", "submenu")
    return props


def _node(item_id: int, props: dict, children: list) -> GLib.Variant:
    kids = [GLib.Variant("v", _node(c.id, item_props(c), c.children)) for c in children]
    return GLib.Variant("(ia{sv}av)", (item_id, props, [k.get_variant() for k in kids]))


def build_node(item: MenuItem, root: bool = False) -> GLib.Variant:
    return _node(item.id, item_props(None if root else item), item.children)


def build_layout(items: list[MenuItem]) -> GLib.Variant:
    return _node(0, item_props(None), items)


def flatten(items: list[MenuItem]) -> dict[int, MenuItem]:
    out = {}
    for item in items:
        out[item.id] = item
        out.update(flatten(item.children))
    return out
