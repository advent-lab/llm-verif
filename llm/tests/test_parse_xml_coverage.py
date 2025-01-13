import sys
from pathlib import Path

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

import unittest
import os
from tempfile import NamedTemporaryFile
from typing import List
from src.questasim import QuestaSim  # Replace with the actual module name

class TestParseCoverageReport(unittest.TestCase):
    def setUp(self):
        # Create a temporary mock coverage XML file based on the provided coverage report
        self.mock_coverage_file = NamedTemporaryFile(delete=False, mode='w', suffix='.xml')
        self.mock_coverage_file.write("""<?xml version="1.0"?>
<coverage_report questa_version="2023.3" command="coverage report -output all_du_coverage.txt -du=* -detail -annotate -code s -xml">
<code_coverage_report lines="1" byDU="1">
    <DuData du="sha1">
        <sourceTable files="1">
            <fileMap fn="0" path="sha1.v"/>
        </sourceTable>
        <statements active="45" hits="40" percent="88.88"/>
    </DuData>
    <DuData du="sha1_core">
        <sourceTable files="1">
            <fileMap fn="0" path="sha1_core.v"/>
        </sourceTable>
        <statements active="144" hits="137" percent="95.13"/>
    </DuData>
    <DuData du="sha1_w_mem">
        <sourceTable files="1">
            <fileMap fn="0" path="sha1_w_mem.v"/>
        </sourceTable>
        <statements active="90" hits="90" percent="100.00"/>
    </DuData>
</code_coverage_report>
</coverage_report>
        """)
        self.mock_coverage_file.close()

    def tearDown(self):
        # Remove the temporary file after the test
        os.remove(self.mock_coverage_file.name)

    def test_parse_coverage_report(self):
        # Expected values
        expected_total_coverage = 95.69  # (40 + 137 + 90) / (45 + 144 + 90) * 100
        expected_coverage_list = [
            {'path': 'sha1.v', 'du': 'sha1', 'coverage': {'active': 45, 'hits': 40, 'percent': 88.88}},
            {'path': 'sha1_core.v', 'du': 'sha1_core', 'coverage': {'active': 144, 'hits': 137, 'percent': 95.13}},
            {'path': 'sha1_w_mem.v', 'du': 'sha1_w_mem', 'coverage': {'active': 90, 'hits': 90, 'percent': 100.00}}
        ]

        # Call the function under test
        questa_sim = QuestaSim("dummy/path")  # Path isn't used for this function
        coverage_list, total_coverage = questa_sim.parse_coverage_report(self.mock_coverage_file.name)

        # Assert total coverage
        self.assertAlmostEqual(total_coverage, expected_total_coverage, places=1)

        # Assert coverage list
        self.assertEqual(len(coverage_list), len(expected_coverage_list))
        for actual, expected in zip(coverage_list, expected_coverage_list):
            self.assertEqual(actual['path'], expected['path'])
            self.assertEqual(actual['du'], expected['du'])
            self.assertEqual(actual['coverage']['active'], expected['coverage']['active'])
            self.assertEqual(actual['coverage']['hits'], expected['coverage']['hits'])
            self.assertAlmostEqual(actual['coverage']['percent'], expected['coverage']['percent'], places=1)

if __name__ == '__main__':
    unittest.main()