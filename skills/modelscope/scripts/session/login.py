import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.stdio import main, run_login

if __name__ == "__main__":
    main("modelscope.session.login", run_login)
