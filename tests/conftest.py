import sys
from pathlib import Path

# Ensure tests can import local modules when pytest adjusts sys.path.
# Insert repo root at the front of sys.path so bare-module imports like
# `import storage` work during test collection.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
