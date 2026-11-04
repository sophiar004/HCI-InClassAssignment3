"""Launch the Haven touchscreen UI from the repository root."""

import sys
from pathlib import Path

# Ensure repository root is on sys.path
repo_root = Path(__file__).resolve().parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from haven.app import main


if __name__ == "__main__":
    main()
