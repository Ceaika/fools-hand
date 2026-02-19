import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ui.app import run

if __name__ == "__main__":
    run()