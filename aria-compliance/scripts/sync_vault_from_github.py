"""
sync_vault_from_github.py
Pulls the Obsidian vault from a private GitHub repository.

SME workflow (zero git knowledge required):
  1. Install the "Obsidian Git" community plugin in their Obsidian vault.
  2. Configure: auto-commit interval = 5 min, auto-push = enabled.
  3. Point the plugin at a private GitHub repo (OBSIDIAN_GITHUB_REPO).
  4. From then on: SME just edits notes in Obsidian. The plugin silently
     commits and pushes changes. Obsidian Sync keeps their devices in sync
     as normal. Nothing else required from the SME.

Server side (Railway):
  - On first run: clones the repo into obsidian-vault/
  - On subsequent runs: git pull --ff-only to get latest notes
  - obsidian_to_graph.py and embed_documents.py then read obsidian-vault/
    exactly as before — no other changes needed in the pipeline.

Required environment variables:
  OBSIDIAN_GITHUB_REPO   e.g. "myorg/aria-obsidian-vault"
  GITHUB_TOKEN           Personal Access Token with repo (read) scope
"""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
BASE_DIR   = SCRIPT_DIR.parent
VAULT_DIR  = BASE_DIR / "obsidian-vault"

load_dotenv(dotenv_path=BASE_DIR / ".env")


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def clone_url(repo: str, token: str) -> str:
    """Embed token into HTTPS URL — no SSH key needed on Railway."""
    return f"https://{token}@github.com/{repo}.git"


def main():
    repo  = os.environ.get("OBSIDIAN_GITHUB_REPO", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    if not repo:
        print("ERROR: OBSIDIAN_GITHUB_REPO not set (e.g. 'myorg/aria-obsidian-vault')")
        sys.exit(1)
    if not token:
        print("ERROR: GITHUB_TOKEN not set — create a PAT with repo (read) scope")
        sys.exit(1)

    url = clone_url(repo, token)

    if not VAULT_DIR.exists() or not (VAULT_DIR / ".git").exists():
        print(f"First run — cloning {repo} into {VAULT_DIR} ...")
        code, out = run(["git", "clone", url, str(VAULT_DIR)])
        if code != 0:
            print(f"ERROR: git clone failed:\n{out}")
            sys.exit(1)
        print("Clone complete.")
    else:
        print(f"Pulling latest from {repo} ...")
        # Update the remote URL in case token changed
        run(["git", "remote", "set-url", "origin", url], cwd=VAULT_DIR)
        code, out = run(["git", "pull", "--ff-only"], cwd=VAULT_DIR)
        if code != 0:
            # Non-fatal: keep going with whatever is already in the vault
            print(f"WARNING: git pull failed (using cached vault):\n{out}")
        else:
            print(f"Pull complete. {out}")

    notes = list(VAULT_DIR.rglob("*.md"))
    print(f"Vault ready — {len(notes)} note(s) in {VAULT_DIR}")


if __name__ == "__main__":
    main()
