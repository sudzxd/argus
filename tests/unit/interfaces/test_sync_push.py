"""Tests for the sync_push entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from argus.interfaces.sync_push import run


class TestSyncPushRun:
    @patch("argus.interfaces.sync_push.SelectiveGitBranchSync")
    @patch("argus.interfaces.sync_push.GitHubClient")
    @patch("argus.interfaces.sync_push.load_argus_config")
    def test_run_success(
        self,
        mock_load_config: MagicMock,
        mock_client_cls: MagicMock,
        mock_sync_cls: MagicMock,
    ) -> None:
        mock_load_config.return_value.storage_dir = ".argus-artifacts"
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
