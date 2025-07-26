# These are the supporting functions for writing evaluation scripts

import numpy as np
import pandas as pd
import time
from llm_verif.questasim import CoverageResponse

class Record:
    def __init__(self, design_name: str, identifier: str, temp_func: str, testplan: bool, batch_size: int, remove_polluted_context: bool, run_type: str = "RUN", include_merge_coverage: bool = False):
        """
        Initialize the Record object.

        Args:
            design_name (str): Name of the design being evaluated.
            temp_func (string): The type of temperature function
            testplan (bool): Indicates whether this run features a testplan
            batch_size (int): The batch size (best of 5)
            remove_polluted_context: Whether or not polluted context is being removed 
            run_type (str): Type of run ("RUN" or "EVAL").
            include_merge_coverage (bool): Whether to include merge coverage columns in the dataframe.
        """
        self.run_type = run_type
        self.design_name = design_name
        self.include_merge_coverage = include_merge_coverage
        self.temp_func = temp_func
        self.testplan = testplan
        self.batch_size = batch_size
        self.remove_polluted_context = remove_polluted_context
        self.identifier = identifier
        self.date = time.strftime("%Y/%m/%d")
        self.start_time = time.strftime("%H:%M:%S")

        # Base columns for the dataframe
        base_columns = [
            "design",
            "date",
            "start time of run",
            "ID",
            "temperature func",
            "testplan",
            "b5",
            "remove polluted contxt",
            "run #",
            "iteration #",
            "batch #",
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

    def update_dataframe(self, coverage: CoverageResponse, temperature: float, top_p: float, run: int, iteration: int, batch_num: int, tokens: int, time: float):
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
            "date": self.date,
            "start time of run": self.start_time,
            "ID": self.identifier,
            "temperature func": self.temp_func,
            "testplan": 1 if self.testplan == True else 0,
            "b5": 1 if self.batch_size > 1 else 0,
            "remove polluted contxt": 1 if self.remove_polluted_context == True else 0,
            "run #": run,
            "iteration #": iteration,
            "batch #": batch_num,
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

        self.df = pd.concat([self.df, pd.DataFrame([data])], ignore_index=True)

        if coverage.total_coverage >= self.max_cov:
            self.max_cov = coverage.total_coverage

        print(self.df)

    def reset_run(self):
        self.start_time = time.strftime("%H:%M:%S")
        self.total_fail = 0
        self.total_pass = 0
        self.max_cov = 0
        self.num_compile_fail = 0
        self.num_decode_fail = 0
        self.num_report_fail = 0
        self.num_sim_fail = 0
        self.num_timeout_fail = 0

    def update_run_average_total_coverage(self, run_id: int):
        if self.run_type == "RUN":
            # Select rows where "run #" matches the given run_id
            run = self.df[self.df["run #"] == run_id]
            
            # Calculate the average statement coverage for this run
            run_coverages = run["statement coverage"].values
            average_coverage = np.average([x for x in run_coverages if x != 0])
            
            # Update the "average total coverage" column for all matching rows
            self.df.loc[self.df["run #"] == run_id, "average total coverage"] = average_coverage # type: ignore

            print(self.df)

    def update_all_average_total_coverage(self):
        if self.run_type == "RUN":
            all_coverages = self.df["statement coverage"].values
            average_coverage = np.average([x for x in all_coverages if x != 0])
            
            # Update the "average total coverage" column for all matching rows
            self.df["average total coverage"] = average_coverage

            print(self.df)

    def update_run_max_coverage(self, run_id: int):
        if self.run_type == "RUN":
            run = self.df[self.df["run #"] == run_id]

            statement_coverage = run["statement coverage"].values
            max_coverage = np.max(np.array(statement_coverage, dtype=float))

            self.df.loc[self.df["run #"] == run_id, "max total coverage"] = max_coverage

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

        print(self.df)

    def update_run_merge_coverage(self, coverage: CoverageResponse, run: int):
        """
        Update the dataframe with merged run coverage results.

        Args:
            coverage (CoverageResponse): The coverage response from merged iterations.
        """
        if self.run_type == "RUN" and self.include_merge_coverage:
            self.df.loc[self.df['run #'] == run, 'run merged coverage'] = coverage.total_coverage

        print(self.df)

