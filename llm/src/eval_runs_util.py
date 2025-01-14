# These are the supporting functions for writing evaluation scripts

import numpy as np
import pandas as pd
from src.evaluation import pass_at_k
from src.questasim import CoverageResponse

class Record:
    def __init__(self, design_name: str, run_type: str = "RUN", include_merge_coverage: bool = False):
        """
        Initialize the Record object.

        Args:
            design_name (str): Name of the design being evaluated.
            run_type (str): Type of run ("RUN" or "EVAL").
            include_merge_coverage (bool): Whether to include merge coverage columns in the dataframe.
        """
        self.run_type = run_type
        self.design_name = design_name
        self.include_merge_coverage = include_merge_coverage

        # Base columns for the dataframe
        base_columns = [
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
        ]

        # Additional columns for run type "RUN"
        if run_type == "RUN":
            additional_columns = [
                "max total coverage",
                "average total coverage",
            ]
            base_columns.extend(additional_columns)

            if self.include_merge_coverage:
                merge_columns = [
                    "run merged coverage",
                    "cross run merged coverage",
                ]
                base_columns.extend(merge_columns)

        self.df = pd.DataFrame(columns=base_columns)

        # Initialize tracking variables
        self.total_pass = 0
        self.total_fail = 0
        self.num_compile_fail = 0
        self.num_sim_fail = 0
        self.num_timeout_fail = 0
        self.num_report_fail = 0
        self.num_decode_fail = 0
        self.max_cov = 0
        self.sum_cov_of_success = 0
        self.avg_total_coverage = 0
        self.tokens_generated = 0
        self.generation_time = 0.0

    def update_dataframe(self, coverage: CoverageResponse, temperature: float, top_p: float, run: int, iteration: int, tokens: int, time: float):
        """
        Update the dataframe with a new record.

        Args:
            coverage (CoverageResponse): The coverage response object.
            temperature (float): Temperature value used in the generation.
            top_p (float): Top-p value used in the generation.
            run (int): Run index.
            iteration (int): Iteration index.
            tokens (int): Tokens generated in the response.
            time (float): Time taken for the generation.
        """
        self.tokens_generated = tokens
        self.generation_time = time

        data = {
            "design": self.design_name,
            "run #": run,
            "iteration #": iteration,
            "temperature": temperature,
            "top_p": top_p,
            "pass": 1 if coverage.success else 0,
            "compile fail": 1 if coverage.error_code == 1 else 0,
            "sim fail": 1 if coverage.error_code == 2 else 0,
            "timeout fail": 1 if coverage.error_code == 3 else 0,
            "report fail": 1 if coverage.error_code == 4 else 0,
            "decode fail": 1 if coverage.error_code == 5 else 0,
            "statement coverage": float(coverage.total_coverage),
            "tokens generated": self.tokens_generated,
            "generation time": self.generation_time,
        }

        if self.run_type == "RUN":
            data.update({
                "max total coverage": self.max_cov,
                "average total coverage": self.avg_total_coverage,
            })

            if self.include_merge_coverage:
                data.update({
                    "run merged coverage": None,  # Placeholder
                    "cross run merged coverage": None,  # Placeholder
                })

        self.df = pd.concat([self.df, pd.DataFrame([data])], ignore_index=True)

    def reset_run(self):
        self.total_fail = 0
        self.total_pass = 0
        self.max_cov = 0
        self.num_compile_fail = 0
        self.num_decode_fail = 0
        self.num_report_fail = 0
        self.num_sim_fail = 0
        self.num_timeout_fail = 0

    def write_to_csv(self, filename: str):
        """
        Write the dataframe to a CSV file.

        Args:
            filename (str): Name of the file to write.
        """
        self.df.to_csv(filename, index=False)

    def update_cross_run_merge_coverage(self, coverage: CoverageResponse):
        """
        Update the dataframe with cross-run merged coverage results.

        Args:
            coverage (CoverageResponse): The coverage response from merged runs.
        """
        if self.run_type == "RUN" and self.include_merge_coverage:
            self.df["cross run merged coverage"] = coverage.total_coverage

