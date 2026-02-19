"""Tests for the sync_push entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from argus.interfaces.sync_push import _require_env, run
from argus.shared.exceptions import ConfigurationError


class TestRequireEnv:
    def test_returns_value_when_set(self) -> None:
        with patch.dict("os.environ", {"MY_VAR": "hello"}):
            assert _require_env("MY_VAR") == "hello"

    def test_raises_when_missing(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(ConfigurationError, match="MY_VAR"),
        ):
            _require_env("MY_VAR")

    def test_raises_when_empty(self) -> None:
        with (
            patch.dict("os.environ", {"MY_VAR": ""}),
            pytest.raises(ConfigurationError, match="MY_VAR"),
        ):
            _require_env("MY_VAR")


class TestSyncPushRun:
    @patch("argus.interfaces.sync_push.SelectiveGitBranchSync")
    @patch("argus.interfaces.sync_push.GitHubClient")
    def test_run_success(
        self, mock_client_cls: MagicMock, mock_sync_cls: MagicMock
    ) -> None:
        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "tok", "GITHUB_REPOSITORY": "o/r"},
        ):
            run()
        mock_client_cls.assert_called_once()
        mock_sync_cls.return_value.push.assert_called_once()

    def test_run_missing_env_exits(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(SystemExit, match="1"),
        ):
            run()
