"""Safe loader for the proven bridge engine kept beside MuslimSim."""

from __future__ import annotations

import importlib.util
from contextlib import contextmanager
from pathlib import Path
import sys
from types import ModuleType
from typing import Iterator, Sequence


class BridgeEngineError(RuntimeError):
    """The adjacent bridge engine cannot be found or loaded safely."""


def engine_path() -> Path:
    """Return the MuslimSim-managed bridge, with the proven root bridge as fallback."""
    project_root = Path(__file__).resolve().parents[2]
    managed = project_root / "bridge" / "final.py"
    if managed.is_file():
        return managed
    # A fresh installation can still start safely before its managed bridge has
    # been copied.  This keeps the original final.py a recovery path only.
    return project_root.parent / "final.py"


def _require_engine() -> Path:
    path = engine_path()
    if not path.is_file():
        raise BridgeEngineError(
            "The proven bridge engine was not found beside the MuslimSim folder: "
            f"{path}"
        )
    return path


def describe_engine() -> str:
    path = _require_engine()
    size_kib = path.stat().st_size / 1024.0
    return f"Bridge engine: {path} ({size_kib:.0f} KiB)"


def _load_engine() -> ModuleType:
    path = _require_engine()
    spec = importlib.util.spec_from_file_location("_muslimsim_bridge_engine", path)
    if spec is None or spec.loader is None:
        raise BridgeEngineError(f"Could not create a loader for {path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # Show the useful source location, not a launcher mystery.
        raise BridgeEngineError(f"Could not load {path}: {exc}") from exc

    main = getattr(module, "main", None)
    if not callable(main):
        raise BridgeEngineError(f"The bridge engine has no callable main() function: {path}")
    return module


@contextmanager
def _forwarded_argv(path: Path, arguments: Sequence[str]) -> Iterator[None]:
    """Run the unchanged legacy parser with arguments supplied by this launcher."""
    original = sys.argv
    sys.argv = [str(path), *arguments]
    try:
        yield
    finally:
        sys.argv = original


def run_engine(arguments: Sequence[str]) -> int:
    """Load and execute final.py in-process without duplicating hardware code."""
    path = _require_engine()
    module = _load_engine()
    try:
        with _forwarded_argv(path, arguments):
            result = module.main()
    except SystemExit as exc:
        # argparse's --help exits this way; keep it a normal launcher result.
        return int(exc.code) if isinstance(exc.code, int) else 0
    except BridgeEngineError:
        raise
    except Exception as exc:
        raise BridgeEngineError(f"Bridge engine stopped with an error: {exc}") from exc
    return int(result) if result is not None else 0
