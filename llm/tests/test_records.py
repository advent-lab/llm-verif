import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
from src.eval_runs_util import Record

class TestRecord(unittest.TestCase):
    def setUpNoMergeCoverage(self):
        
        record = Record("test_design", "RUN", False)

        columns = record.df.columns

        assert columns == [
            "design",
            "run #",
            "iteration #",
            "temperature",
            "top_p",
            "pass",
            "compile fail",
            "sim fail",
            "timeout fail",
            "report fail",
            "decode fail",
            "statement coverage",
            "tokens generated",
            "generation time",
            "max total coverage",
            "average total coverage",
        ]

    def setUpMergeCoverage(self):
        
        record = Record("test_design", "RUN", True)

        columns = record.df.columns

        assert columns == [
            "design",
            "run #",
            "iteration #",
            "temperature",
            "top_p",
            "pass",
            "compile fail",
            "sim fail",
            "timeout fail",
            "report fail",
            "decode fail",
            "statement coverage",
            "tokens generated",
            "generation time",
            "max total coverage",
            "average total coverage",
            "run merged coverage",
            "cross run merged coverage",
        ]