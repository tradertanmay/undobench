"""Git repository domain sandbox."""

from __future__ import annotations
import os
import pathlib
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional


class GitWorkspaceSandbox:
    """Manages an isolated Git repository workspace for code operations."""

    def __init__(self, workspace_path: Optional[str] = None):
        if workspace_path is None:
            self._tmp_dir = tempfile.mkdtemp(prefix="rb_git_")
            self.workspace_dir = pathlib.Path(self._tmp_dir)
        else:
            self._tmp_dir = None
            self.workspace_dir = pathlib.Path(workspace_path)
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self._init_repo()

    def _run_git(self, *args: str) -> str:
        res = subprocess.run(
            ["git", *args],
            cwd=str(self.workspace_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()

    def _init_repo(self) -> None:
        self._run_git("init", "-b", "main")
        self._run_git("config", "user.name", "RecoverBench Agent")
        self._run_git("config", "user.email", "agent@recoverbench.local")
        self._run_git("config", "commit.gpgsign", "false")

    def seed_file(self, relative_path: str, content: str, commit_message: Optional[str] = None) -> None:
        file_path = self.workspace_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        if commit_message:
            self._run_git("add", relative_path)
            self._run_git("commit", "-m", commit_message)

    # --- Tool Callables ---

    def write_workspace_file(self, relative_path: str, content: str) -> Dict[str, Any]:
        """Tool: Write or overwrite a file in the workspace."""
        file_path = self.workspace_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return {"path": relative_path, "bytes_written": len(content.encode("utf-8"))}

    def commit_changes(self, message: str, paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """Tool: Stage files and create a git commit."""
        if paths:
            for p in paths:
                self._run_git("add", p)
        else:
            self._run_git("add", "-A")

        output = self._run_git("commit", "-m", message)
        commit_hash = self._run_git("rev-parse", "HEAD")
        return {"commit_hash": commit_hash, "message": message, "raw": output}

    def create_branch(self, branch_name: str) -> Dict[str, Any]:
        """Tool: Create and switch to a new git branch."""
        self._run_git("checkout", "-b", branch_name)
        return {"branch": branch_name, "status": "CREATED"}

    def merge_branch(self, branch_name: str, fast_forward: bool = True) -> Dict[str, Any]:
        """Tool: Merge branch into current branch."""
        args = ["merge"]
        if fast_forward:
            args.append("--ff-only")
        args.append(branch_name)
        out = self._run_git(*args)
        return {"merged_branch": branch_name, "raw": out}

    def create_tag(self, tag_name: str, message: str = "") -> Dict[str, Any]:
        """Tool: Create annotated or lightweight git tag."""
        if message:
            self._run_git("tag", "-a", tag_name, "-m", message)
        else:
            self._run_git("tag", tag_name)
        return {"tag": tag_name, "status": "CREATED"}

    def cherry_pick_commit(self, commit_hash: str) -> Dict[str, Any]:
        """Tool: Cherry pick commit onto current branch."""
        out = self._run_git("cherry-pick", commit_hash)
        return {"cherry_picked": commit_hash, "raw": out}

    # --- Oracle Inspection Methods ---

    def query_commit_count(self) -> int:
        try:
            out = self._run_git("rev-list", "--count", "HEAD")
            return int(out)
        except Exception:
            return 0

    def query_latest_commit_message(self) -> Optional[str]:
        try:
            return self._run_git("log", "-1", "--pretty=%B")
        except Exception:
            return None

    def query_file_content(self, relative_path: str) -> Optional[str]:
        file_path = self.workspace_dir / relative_path
        return file_path.read_text(encoding="utf-8") if file_path.exists() else None

    def is_working_tree_clean(self) -> bool:
        status = self._run_git("status", "--porcelain")
        return len(status.strip()) == 0

    def query_tag_count(self) -> int:
        try:
            tags = self._run_git("tag").splitlines()
            return len([t for t in tags if t.strip()])
        except Exception:
            return 0

    def get_full_state(self) -> Dict[str, Any]:
        return {
            "commit_count": self.query_commit_count(),
            "latest_commit": self.query_latest_commit_message(),
            "is_clean": self.is_working_tree_clean(),
            "tag_count": self.query_tag_count(),
        }

    def cleanup(self) -> None:
        if self._tmp_dir and os.path.exists(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
