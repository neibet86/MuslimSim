"""Smoke test for the community profile system."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from muslimsim.hardware.catalog import device_by_key, catalogue_snapshot
from muslimsim.hardware.product_registry import PRODUCTS, products_for_usb

# Registry extension
total = len(PRODUCTS)
print(f"Total products in registry: {total}")
assert total >= 24, f"Expected >= 24, got {total}"

honeycomb = products_for_usb(0x294B, 0x0070)
assert honeycomb and honeycomb[0].key == "honeycomb_alpha", "Honeycomb not in registry"
print(f"Honeycomb Alpha USB lookup: {honeycomb[0].key} OK")

winctrl = products_for_usb(0x4098, 0xBB35)
assert winctrl and winctrl[0].key == "pfp3n_bb35", "Built-in PFP3N broken"
print(f"WINCTRL PFP3N USB lookup: {winctrl[0].key} OK")

# Catalog fallback
d = device_by_key("honeycomb_alpha")
assert d is not None, "honeycomb_alpha not found via device_by_key"
assert len(d.controls) > 0, "no controls loaded"
print(f"device_by_key(honeycomb_alpha): {d.title}, {len(d.controls)} controls OK")

d2 = device_by_key("honeycomb_alpha_xl")
assert d2 is not None and d2.key == "honeycomb_alpha", "alias not resolved"
print(f"alias honeycomb_alpha_xl -> {d2.key} OK")

d3 = device_by_key("pap3_mag")
assert d3 is not None, "built-in pap3_mag broken"
print(f"built-in pap3_mag: {d3.title} OK")

# Catalogue snapshot includes community
snap = catalogue_snapshot()
titles = [x["title"] for x in snap["devices"]]
assert any("Honeycomb" in t for t in titles), "Honeycomb missing from snapshot"
assert any("Multi Panel" in t for t in titles), "Multi Panel missing from snapshot"
print(f"catalogue_snapshot: {len(snap['devices'])} total devices, community included OK")

# Default roles carried through
honey_device = next(x for x in snap["devices"] if x["key"] == "honeycomb_alpha")
aileron = next((c for c in honey_device["controls"] if c["key"] == "axis_aileron"), None)
assert aileron and aileron["default_role"], "default_role missing for aileron"
print(f"default_role for axis_aileron: {aileron['default_role']} OK")

# Keys are unique — no community key shadows a built-in
built_in_keys = {x["key"] for x in snap["devices"][:len(snap["devices"]) - 6]}
community_keys = {"honeycomb_alpha", "honeycomb_bravo", "logitech_saitek_multi_panel",
                  "logitech_x52_pro", "thrustmaster_tca_airbus", "virpil_vpc_alpha"}
assert not built_in_keys & community_keys, "Community key collision with built-in"
print("No key collisions with built-ins OK")

print("\nAll community profile smoke tests passed.")
