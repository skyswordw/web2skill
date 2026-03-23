import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.stdio import main, run_capability

if __name__ == "__main__":
    main("modelscope.get_token", lambda: run_capability("modelscope.get_token", "get_token"))
