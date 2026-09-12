"""Device launch modules.  Each maps a UI/launcher choice to bridge options."""

from . import agp, pdc, pedals, pfp, pu_overhead, winctrl

ALL_DEVICES = (
    pu_overhead.DESCRIPTOR,
    winctrl.DESCRIPTOR,
    pdc.DESCRIPTOR,
    pedals.DESCRIPTOR,
    agp.DESCRIPTOR,
    pfp.DESCRIPTOR,
)

__all__ = (
    "ALL_DEVICES",
    "agp",
    "pdc",
    "pedals",
    "pfp",
    "pu_overhead",
    "winctrl",
)
