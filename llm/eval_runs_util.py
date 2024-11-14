# These are the supporting functions for writing evaluation scripts

import numpy as np
import pandas as pd
from evaluation import pass_at_k
from questasim import CoverageResponse

class Record:
    def __init__(self, design_name: str, run_type: str = "RUN"):

        self.run_type = run_type

        self.design_name = design_name

        if run_type == "RUN":
            self.df = pd.DataFrame(columns=[
                "design",
                "run #",
                "iteration #",
                "temperature", 
                "top_p", 
                "pass",
                "pass@1",
                "pass@5",
                "pass@8",
                "pass@10",
                "compile fail",
                "sim fail",
                "timeout fail",
                "report fail",
                "decode fail",
                "statement coverage",
                "max total coverage",
                "average total coverage",
                "tokens generated",
                "generation time"
            ])
        elif run_type == "EVAL":
            self.df = pd.DataFrame(columns=[
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
                "generation time"
            ])

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

    def update_dataframe(self, coverage: CoverageResponse, temperature: int, top_p: int, run: int, iteration: int, tokens: int, time: float):
        self.tokens_generated = tokens
        self.generation_time = time
        
        if self.run_type == "RUN":
            if coverage.success:
                print(f"Passed!\n{coverage.error_message}")
                self.total_pass = self.total_pass + 1
                self.sum_cov_of_success = self.sum_cov_of_success + float(coverage.total_coverage)
                if float(coverage.total_coverage) > self.max_cov:
                    self.max_cov = float(coverage.total_coverage)
            else:
                print(f"Failed!\n{coverage.error_message}")
                self.total_fail = self.total_fail + 1
                if coverage.error_code == 1:
                    self.num_compile_fail = self.num_compile_fail + 1
                elif coverage.error_code == 2:
                    self.num_sim_fail = self.num_sim_fail + 1
                elif coverage.error_code == 3:
                    self.num_timeout_fail = self.num_timeout_fail + 1
                else:
                    self.num_decode_fail = self.num_decode_fail + 1
            
            self.df = pd.concat([self.df, pd.DataFrame([{
                "design": self.design_name,
                "run #": run,
                "iteration #": iteration,
                "temperature": temperature, 
                "top_p": top_p, 
                "pass": 1 if coverage.success == True else 0,
                "pass@1": pass_at_k((self.total_pass + self.total_fail), self.total_pass, 1),
                "pass@5": pass_at_k((self.total_pass + self.total_fail), self.total_pass, 5),
                "pass@8": pass_at_k((self.total_pass + self.total_fail), self.total_pass, 10),
                "pass@10": pass_at_k((self.total_pass + self.total_fail), self.total_pass, 25),
                "compile fail": 1 if coverage.error_code == 1 else 0,
                "sim fail": 1 if coverage.error_code == 2 else 0,
                "timeout fail": 1 if coverage.error_code == 3 else 0,
                "report fail": 1 if coverage.error_code == 4 else 0,
                "decode fail": 1 if coverage.error_code == 5 else 0,
                "statement coverage": float(coverage.total_coverage),
                "max total coverage": self.max_cov,
                "tokens generated": self.tokens_generated,
                "generation time": self.generation_time
            }])], ignore_index=True)  # Appending to df
            print(self.df)
        elif self.run_type == "EVAL":
            self.df = pd.concat([self.df, pd.DataFrame([{
                "design": self.design_name,
                "temperature": temperature,
                "top_p": top_p,
                "pass": 1 if coverage.success == True else 0,
                "compile fail": 1 if coverage.error_code == 1 else 0,
                "sim fail": 1 if coverage.error_code == 2 else 0,
                "timeout fail": 1 if coverage.error_code == 3 else 0,
                "report fail": 1 if coverage.error_code == 4 else 0,
                "decode fail": 1 if coverage.error_code == 5 else 0,
                "statement coverage": float(coverage.total_coverage),
                "tokens generated": self.tokens_generated,
                "generation time": self.generation_time
            }])])

    def reset_run(self):
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
            self.df.loc[self.df["run #"] == run_id, "average total coverage"] = average_coverage

    def update_all_average_total_coverage(self):
        if self.run_type == "RUN":
            all_coverages = self.df["statement coverage"].values
            average_coverage = np.average([x for x in all_coverages if x != 0])
            
            # Update the "average total coverage" column for all matching rows
            self.df["average total coverage"] = average_coverage

    def write_to_csv(self, filename: str):
        self.df.to_csv(filename, index=False)        
