import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

print("importing...", flush=True)
from src.ui.app import run
print("starting...", flush=True)

if __name__ == "__main__":
    run()