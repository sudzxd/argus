"""Unified entry point — dispatches to the appropriate mode.

Reads ``INPUT_MODE`` from the environment and runs the corresponding
pipeline:

- ``review`` (default): PR review pipeline
- ``index``: Incremental codebase index (pulls, updates changed files, pushes)
- ``bootstrap``: Full codebase index from scratch (+ push to argus-data)
"""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

_VALID_MODES = {"review", "index", "bootstrap"}


def main() -> None:
    """Dispatch to the appropriate entry point based on INPUT_MODE."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    mode = os.environ.get("INPUT_MODE", "review").strip().lower()

    if mode not in _VALID_MODES:
        valid = ", ".join(sorted(_VALID_MODES))
        logger.error("Unknown mode: %r (valid: %s)", mode, valid)
        sys.exit(1)

    if mode == "review":
        from argus.interfaces.action import run

        run()
    elif mode == "index":
        from argus.interfaces.sync_index import run

        run()
    elif mode == "bootstrap":
        from argus.interfaces.bootstrap import run as bootstrap_run
        from argus.interfaces.sync_push import run as push_run

        bootstrap_run()
        push_run()


if __name__ == "__main__":
    main()
