"""Run the reminder evaluation using the Part 1B project directory."""

import os
from pathlib import Path

from reminder_agent.evaluation.run import main


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    raise SystemExit(main())
