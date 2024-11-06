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
                "pass rate",
                "pass@1",
                "pass@5",
                "pass@8",
                "pass@10",
                "compile fails",
                "sim fails",
                "timeout fails",
                "report fails",
                "decode fails",
                "compile fail rate",
                "sim fail rate",
                "timeout fail rate",
                "report fail rate",
                "decode fail rate",
                "statement coverage",
                "max total coverage",
                "average total coverage",
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
                "statement coverage"
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

    def update_dataframe(self, coverage: CoverageResponse, temperature: int, top_p: int, run: int, iteration: int):
        if self.run_type == "RUN":
            if coverage.success:
                print(f"Passed!\n{coverage.error_message}")
                self.total_pass = self.total_pass + 1
                self.sum_cov_of_success = self.sum_cov_of_success + int(coverage.total_coverage)
                if int(coverage.total_coverage) > self.max_cov:
                    self.max_cov = int(coverage.total_coverage)
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
                "pass rate": self.total_pass / (self.total_pass + self.total_fail) if (self.total_pass + self.total_fail) != 0 else 0,
                "pass@1": pass_at_k((self.total_pass + self.total_fail), self.total_pass, 1),
                "pass@5": pass_at_k((self.total_pass + self.total_fail), self.total_pass, 5),
                "pass@8": pass_at_k((self.total_pass + self.total_fail), self.total_pass, 10),
                "pass@10": pass_at_k((self.total_pass + self.total_fail), self.total_pass, 25),
                "compile fails": self.num_compile_fail,
                "sim fails": self.num_sim_fail,
                "timeout fails": self.num_timeout_fail,
                "report fails": self.num_report_fail,
                "decode fails": self.num_decode_fail,
                "compile fail rate": self.num_compile_fail / (self.total_pass + self.total_fail) if (self.total_pass + self.total_fail) != 0 else 0,
                "sim fail rate": self.num_sim_fail / (self.total_pass + self.total_fail) if (self.total_pass + self.total_fail) != 0 else 0,
                "timeout fail rate": self.num_timeout_fail / (self.total_pass + self.total_fail) if (self.total_pass + self.total_fail) != 0 else 0,
                "report fail rate": self.num_report_fail / (self.total_pass + self.total_fail) if (self.total_pass + self.total_fail) != 0 else 0,
                "decode fail rate": self.num_decode_fail / (self.total_fail + self.total_pass) if (self.total_pass + self.total_fail) != 0 else 0,
                "statement coverage": int(coverage.total_coverage),
                "max total coverage": self.max_cov
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
                "statement coverage": coverage.total_coverage
            }])])

    def update_average_total_coverage(self):
        if self.run_type == "RUN":
            self.df["average total coverage"] = self.sum_cov_of_success / self.total_pass if self.total_pass != 0 else 0
            print(self.df)

    def write_to_csv(self, filename: str):
        self.df.to_csv(filename, index=False)        
