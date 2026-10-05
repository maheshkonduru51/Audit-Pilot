from __future__ import annotations

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(root / "seed.py")], check=True)
print("Demo smoke test seed complete.")
print("Next: start FastAPI, then Streamlit, login as analyst and try the README demo prompts.")
