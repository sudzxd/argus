"""Tests for the unified entry point dispatcher."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from argus.interfaces.main import _VALID_MODES, main


class TestMainDispatch:
    def test_valid_modes_set(self) -> None:
        assert {"review", "index", "bootstrap"} == _VALID_MODES

    @patch("argus.interfaces.main.os.environ", {"INPUT_MODE": "review"})
    @patch("argus.interfaces.action.run")
    def test_dispatch_review(self, mock_run: object) -> None:
        main()
        from argus.interfaces.action import run

        run.assert_called_once()  # type: ignore[union-attr]

    @patch("argus.interfaces.main.os.environ", {"INPUT_MODE": "index"})
    @patch("argus.interfaces.sync_index.run")
    def test_dispatch_index(self, mock_run: object) -> None:
        main()
        from argus.interfaces.sync_index import run

        run.assert_called_once()  # type: ignore[union-attr]

    @patch("argus.interfaces.main.os.environ", {"INPUT_MODE": "bootstrap"})
    @patch("argus.interfaces.bootstrap.run")
    @patch("argus.interfaces.sync_push.run")
    def test_dispatch_bootstrap(self, mock_push: object, mock_boot: object) -> None:
        main()
        from argus.interfaces.bootstrap import run as boot

        boot.assert_called_once()  # type: ignore[union-attr]
        from argus.interfaces.sync_push import run as push

        push.assert_called_once()  # type: ignore[union-attr]

    @patch("argus.interfaces.main.os.environ", {})
    @patch("argus.interfaces.action.run")
    def test_default_mode_is_review(self, mock_run: object) -> None:
        main()
        from argus.interfaces.action import run

        run.assert_called_once()  # type: ignore[union-attr]

    @patch("argus.interfaces.main.os.environ", {"INPUT_MODE": "invalid"})
    def test_invalid_mode_exits(self) -> None:
        with pytest.raises(SystemExit, match="1"):
            main()

    @patch("argus.interfaces.main.os.environ", {"INPUT_MODE": "  Review  "})
    @patch("argus.interfaces.action.run")
    def test_mode_is_stripped_and_lowered(self, mock_run: object) -> None:
        main()
        from argus.interfaces.action import run

        run.assert_called_once()  # type: ignore[union-attr]
