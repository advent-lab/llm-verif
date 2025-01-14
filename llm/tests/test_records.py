import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
from src.eval_runs_util import Record

class TestRecord(unittest.TestCase):
    def setUpNoMergeCoverage(self):
        
        record = Record("test_design", "RUN", False)

        self.a