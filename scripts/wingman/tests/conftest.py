import sys
from pathlib import Path

# `scripts/` is the import root for repository tooling (package `wingman`); it is
# deliberately not on the backend package path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
