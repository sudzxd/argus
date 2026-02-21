"""Push local artifacts to the argus-data branch.

Usage:
    GITHUB_TOKEN=... GITHUB_REPOSITORY=owner/repo \
    uv run python -m argus.interfaces.sync_push
"""

from __future__ import annotations

import logging
import sys

from pathlib import Path

from argus.infrastructure.constants import DATA_BRANCH
from argus.infrastructure.github.client import GitHubClient
from argus.infrastructure.storage.git_branch_store import SelectiveGitBranchSync
from argus.interfaces.env_utils import require_env
from argus.interfaces.toml_config import load_argus_config
from argus.shared.exceptions import ArgusError

logger = logging.getLogger(__name__)


def run() -> None:
    """Push artifacts from storage_dir to the argus-data branch."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        cfg = load_argus_config("index")
        token = require_env("GITHUB_TOKEN")
        repo = require_env("GITHUB_REPOSITORY")
        storage_dir = Path(cfg.storage_dir)

        client = GitHubClient(token=token, repo=repo)
        sync = SelectiveGitBranchSync(
            client=client,
            branch=DATA_BRANCH,
            storage_dir=storage_dir,
        )
        sync.push()
    except ArgusError as e:
        logger.error("Sync push failed: %s", e)
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    run()
