"""Simulator-facing shared services for MuslimSim.

Hardware ownership stays in ``muslimsim.devices`` / the bridge.  This package
contains simulator data distribution only.
"""
from .xplane_telemetry import (
    ResourceBackoffError,
    SharedXPlaneTelemetryHub,
    XPlaneSessionResourceCache,
)

__all__ = [
    "ResourceBackoffError",
    "SharedXPlaneTelemetryHub",
    "XPlaneSessionResourceCache",
]
