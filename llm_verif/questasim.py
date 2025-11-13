import os
import logging
import shutil
from llm_verif.simulator import ArtifactPlan, Simulator, CoverageResponse, DU
import re
from typing import List
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Tuple

class QuestaSim(Simulator):

    def __init__(self, simulator_path: str, design_unit: str):
        super().__init__(simulator_path, design_unit)

    def plan_artifacts(self, work_dir: str | Path, tb_stem: str, sim_runs: int) -> ArtifactPlan:
        wd = str(work_dir)
        tb_path = os.path.join(wd, f"{tb_stem}.sv")
        compile_log = os.path.join(wd, f"{tb_stem}_compile.log")
        sim_logs = [os.path.join(wd, f"{tb_stem}_{i}_sim.log") for i in range(sim_runs)]
        per_run_coverage_dbs = [os.path.join(wd, f"{tb_stem}_{i}.ucdb") for i in range(sim_runs)]
        merged_coverage_db = os.path.join(wd, f"{tb_stem}.ucdb") if sim_runs > 1 else per_run_coverage_dbs[0]

        return ArtifactPlan(
            work_dir=wd,
            tb_path=tb_path,
            compile_log=compile_log,
            sim_logs=sim_logs,
            per_run_coverage_dbs=per_run_coverage_dbs,
            merged_coverage_db=merged_coverage_db,
            report_path=os.path.join(wd, f"{tb_stem}_report.xml"),
            annotate_dir=None,
            info_path=None
        )

    @staticmethod
    def cleanup(directory: str):
        """
        Cleanup temporary simulation files.

        Args:
            directory (str): Directory containing temporary files.
        """
        try:
            shutil.rmtree(os.path.join(directory, "work"), ignore_errors=True)
            os.remove(os.path.join(directory, "transcript"))
        except FileNotFoundError:
            pass
        except Exception as e:
            logging.warning(f"Error during cleanup: {e}")

    """
    COMPILING AND SIMULATING
    """
    def compile_design(self, tb_path: str, data_point: dict) -> str:
        """
        Compile the design files.

        Args:
            tb_path (str): Path to the testbench file.
            data_point (dict): Data point for the simulation.

        Returns:
            str: Compilation output.
        """
        logging.debug(f"Compiling testbench: {tb_path}")
        compile_command = self.vlog_builder(tb_path=tb_path, data_point=data_point).split()
        return self.run_command(compile_command)

    def simulate_design(self, testbench_module: str, ucdb_path: str) -> str:
        """
        Run the simulation.

        Args:
            testbench_module (str): Testbench module name.
            ucdb_path (str): Full path for the .ucdb file.

        Returns:
            str: Simulation output.
        """
        questa_dir = self.simulator_path
        command = [
            f'{questa_dir}/vsim',
            f'work.tb_llm',
            '-coverage',
            '-sv_seed',
            'random',
            '-c',
            '-do',
            f'coverage exclude -du tb_llm;coverage save -onexit {ucdb_path};run -all;exit;'
        ]
        return self.run_command(command, timeout=300)

    
    def run_simulation_flow(self, work_dir: str | Path, tb_name: str, data_point: dict[str, str | list[str]] | None, sim_runs: int = 1) -> CoverageResponse:
        """
        Run the complete QuestaSim simulation flow: compile, simulate, generate coverage.

        Args:
            work_dir: Working directory for artifacts
            tb_name: Testbench filename (e.g., "tb_llm_design_0_0_0.sv")
            data_point: Dictionary containing design and context files
            sim_runs: Number of simulation runs to perform

        Returns:
            CoverageResponse with coverage results or error information
        """
        # Extract testbench stem from filename (remove extension)
        tb_stem = os.path.splitext(tb_name)[0]

        # Use ArtifactPlan for systematic file path management
        artifact_plan = self.plan_artifacts(work_dir, tb_stem, sim_runs)

        # Extract paths from artifact plan
        tb_path = artifact_plan.tb_path
        compile_log_path = artifact_plan.compile_log
        coverage_ucdb_path = artifact_plan.merged_coverage_db
        coverage_report_path = artifact_plan.report_path
        
        if not os.path.exists(tb_name):
            raise ValueError(f"Testbench path does not exist: {tb_name}")
        if not data_point:
            raise ValueError("Data point is required for simulation.")
        if sim_runs <= 0:
            raise ValueError("sim_runs must be greater than zero.")

        questa_dir = self.simulator_path
        design_dir = os.path.split(os.path.split(tb_name)[0])[0]
        tb_module_name = self.get_testbench_name(tb_name)

        # Check for $finish in the testbench
        if not self.has_finish(tb_path):
            return CoverageResponse(False, 5, "No $finish found in the test bench. Simulation will not finish.")

        # Cleanup
        self.cleanup(design_dir)

        # Compilation
        try:
            compile_output = self.compile_design(tb_path, data_point)
            with  open(compile_log_path, 'w') as f:
                f.write(compile_output)
            if not QuestaSim.check_errors(compile_output):
                raise RuntimeError(compile_output)
            logging.info("Compilation successful.")
        except RuntimeError as e:
            return CoverageResponse(False, 1, str(e))

        # Simulation phase - run multiple simulations with different seeds
        try:
            for i in range(sim_runs):
                sim_log_path_i = artifact_plan.sim_logs[i]
                ucdb_path_i = artifact_plan.per_run_coverage_dbs[i]

                sim_output = self.simulate_design(tb_module_name, ucdb_path_i)
                with open(sim_log_path_i, 'w') as f:
                    f.write(sim_output)
                if not QuestaSim.check_errors(sim_output):
                    raise RuntimeError(sim_output)
                logging.info(f"Simulation {i + 1}/{sim_runs} successful.")
        except RuntimeError as e:
            logging.error(f"Simulation failed: {e}")
            return CoverageResponse(False, 2, str(e))

        # Coverage generation phase - merge per-run coverage files or use single file
        try:
            if sim_runs > 1:
                # Check that all per-run coverage databases exist
                missing_ucdbs = [f for f in artifact_plan.per_run_coverage_dbs if not os.path.exists(f)]
                if missing_ucdbs:
                    error_msg = f"Coverage database files not found: {missing_ucdbs}"
                    logging.error(error_msg)
                    return CoverageResponse(False, 3, error_msg)

                self.generate_merged_coverage_report(
                    self.design_unit,
                    artifact_plan.per_run_coverage_dbs,
                    coverage_ucdb_path,
                    coverage_report_path
                )
            else:
                # Check single coverage database exists
                if not os.path.exists(artifact_plan.per_run_coverage_dbs[0]):
                    error_msg = f"Coverage database not found: {artifact_plan.per_run_coverage_dbs[0]}"
                    logging.error(error_msg)
                    return CoverageResponse(False, 3, error_msg)

                self.generate_coverage_report(
                    artifact_plan.per_run_coverage_dbs[0],
                    coverage_report_path
                )

            # Check if report was created
            if not os.path.exists(coverage_report_path):
                error_msg = f"Coverage report not created: {coverage_report_path}"
                logging.error(error_msg)
                return CoverageResponse(False, 3, error_msg)

            coverage_list, total_coverage = self.parse_coverage_report(coverage_report_path)
            logging.info("Coverage report generated successfully.")
            return CoverageResponse(True, 0, sim_output, coverage_list, total_coverage)
        except RuntimeError as e:
            return CoverageResponse(False, 3, str(e))
        
    """
    GENERATING REPORTS
    """
    def generate_coverage_report(self, coverage_report_ucdb: str, coverage_report_path: str) -> str:
        """
        Generate the coverage report.

        Args:
            coverage_report_path (str): Path to the coverage report file.

        Returns:
            str: Report generation output.
        """
        questa_dir = self.simulator_path
        command = [
            f'{questa_dir}/vsim',
            '-viewcov',
            f'{coverage_report_ucdb}',
            '-c',
            '-do',
            f'coverage report -output {coverage_report_path} -du=* -detail -annotate -code s -xml;exit;'
        ]
        logging.debug(f"Coverage report command: {' '.join(command)}")
        return self.run_command(command)
    
    def generate_merged_coverage_ucdb(self, du: str, coverage_dbs: List[str], coverage_ucdb_path: str) -> str:
        """
        Generate the coverage report.

        Args:
            du (str): Name of the design unit to be merged
            coverage dbs (List[str]): List of UCDB coverage databases to merge together.
            log_name (str): Log file name.

        Returns:
            str: Report generation output.

        Raises:
            FileNotFoundError: If any coverage database files don't exist
        """
        # Check that all input coverage files exist
        missing_files = [f for f in coverage_dbs if not os.path.exists(f)]
        if missing_files:
            raise FileNotFoundError(f"Coverage database files not found: {missing_files}")

        questa_dir = self.simulator_path
        command = [
            f'{questa_dir}/vcover',
            'merge',
            '-recursive',
            '-out',
            coverage_ucdb_path,
        ] + coverage_dbs

        return self.run_command(command)

    @staticmethod
    def parse_coverage_report(report_path: str) -> tuple[list[DU], float]:
        """
        Parse the coverage report XML and extract coverage details.

        Args:
            report_path (str): Path to the XML report file.

        Returns:
            Tuple[List[dict], float]: List of coverage details and total coverage percentage.
        """
        try:
            xml_tree = ET.parse(report_path)
            root = xml_tree.getroot()

            coverage_list = []
            total_active = 0
            total_hits = 0

            for du_data in root.findall('.//DuData'):
                du_name = du_data.get('du')
                file_map = du_data.find('.//fileMap')
                file_path = file_map.get('path') if file_map is not None else "unknown"

                statements = du_data.find('statements')
                active =  int(statements.get('active', 0)) if statements is not None else 0
                hits = int(statements.get('hits', 0)) if statements is not None else 0
                percent = float(statements.get('percent', 0.0)) if statements is not None else 0
                
                details = du_data.findall('.//stmt')

                total_active += active 
                total_hits += hits

                coverage_list.append(DU(
                    path=str(file_path),
                    du=str(du_name),
                    coverage={
                        'active': active,
                        'hits': hits,
                        'percent': percent
                    },
                    coverage_details=details
                ))

            total_coverage = (total_hits / total_active) * 100.0 if total_active > 0 else 0.0
            return coverage_list, total_coverage
        except ET.ParseError as e:
            logging.error(f"XML Parse Error: {e}")
            return [], 0
        except FileNotFoundError:
            logging.error(f"File not found: {report_path}")
            return [], 0

    def generate_merged_coverage_report(
        self, du: str, coverage_dbs: list[str], coverage_ucdb_path: str, coverage_report_path: str
    ) -> str:
        """
        Generate a merged coverage XML report for a specific design unit.

        This method combines multiple coverage databases (`.ucdb` files) into a single coverage
        report and generates a detailed XML coverage report for the specified design unit.

        Args:
            du (str): The name of the design unit to generate the report for.
            coverage_dbs (List[Union[str, Path]]): A list of paths to coverage databases (`.ucdb` files).
            log_name (str): The base name of the log files to be generated.

        Returns:
            str: The output of the generated XML coverage report.

        Raises:
            TypeError: If `coverage_dbs` is not a homogeneous list of strings or Paths.
            RuntimeError: If an error occurs during the merging or report generation process.
        """
        # Validate input
        if not all(isinstance(val, (str, Path)) for val in coverage_dbs):
            raise TypeError("Argument coverage_dbs should be a list of strings or Paths.")

        try:
            # Merge coverage databases
            merge_output = self.generate_merged_coverage_ucdb(du, coverage_dbs, coverage_ucdb_path)
            if not QuestaSim.check_errors(merge_output):
                raise RuntimeError(f"Error during UCDB merge: {merge_output}")

            # Generate the coverage report
            report_output = self.generate_coverage_report(coverage_ucdb_path, coverage_report_path)
            return report_output
        except Exception as e:
            # Propagate exception for the caller to handle
            raise RuntimeError(f"Failed to generate merged coverage report: {e}") from e


    @staticmethod
    def check_errors(questa_output: str) -> bool:
        if not questa_output:
            return False

        lines = questa_output.splitlines()
        split_line = re.split(r'[#,:]', lines[-1])
        stripped_items = [item.strip() for item in split_line]
        cleaned_items = [x for x in stripped_items if x]
        logging.debug(f"QuestaSim output check: {cleaned_items}")
        
        if len(cleaned_items) != 4:
            return False

        if cleaned_items[0] == 'Errors' and cleaned_items[1] == '0': #and cleaned_items[2] == 'Warnings' and cleaned_items[3] == '0':
            return True

        return False

    

    def vlog_builder(self, tb_path: str, data_point: dict) -> str:
        return f"vlog -sv +cover=s {' '.join(data_point['design_context'])} {' '.join(data_point['design'])} {tb_path}"

    def get_coverage_file_extension(self) -> str:
        """Get the file extension for QuestaSim coverage database files."""
        return ".ucdb"

    def merge_and_parse_run_coverage(
        self, design_name: str, work_dir: str, run_idx: int, max_iterations: int,
        batch_size: int, sim_runs: int, design_dir: str, use_store: bool
    ) -> CoverageResponse:
        """
        Merge QuestaSim coverage for a specific run and parse the result.

        This method uses ArtifactPlan to systematically find all coverage database files
        for a specific run, then merges and parses them.

        Args:
            design_name: Name of the design module
            work_dir: Working directory containing coverage files
            run_index: Index of the current run
            max_iterations: Maximum iterations per run
            batch_size: Batch size per iteration
            sim_runs: Number of simulation runs per testbench
            design_dir: Design directory path (not used, kept for signature compatibility)
            use_store: Whether using file store
        Returns:
            CoverageResponse: Response containing merged coverage data
        """
        try: 
            # Collect all coverage database files using ArtifactPlan
            coverage_dbs = []
            for iter_idx in range(max_iterations):
                for batch_idx in range(batch_size):
                    tb_stem = f"tb_llm_{design_name}_{run_idx}_{iter_idx}_{batch_idx}"
                    artifact_plan = self.plan_artifacts(work_dir, tb_stem, sim_runs)

                    # Collect per-run coverage databases from the artifact plan
                    for cov_db in artifact_plan.per_run_coverage_dbs:
                        if os.path.exists(cov_db):
                            coverage_dbs.append(cov_db)

            if not coverage_dbs:
                logging.warning("No UCDB files found for merging coverage.")
                return CoverageResponse(False, -1, "No coverage files found")

            # Define output paths for merged coverage
            log_name = f"{work_dir}/merged_coverage_{design_name}_run{run_idx}"
            merged_ucdb_path = f"{log_name}.ucdb"
            merged_report_path = f"{log_name}_report.xml"

            # Merge coverage
            merge_output = self.generate_merged_coverage_report(
                self.design_unit,
                coverage_dbs,
                merged_ucdb_path,
                merged_report_path
            )

            logging.info(f"Merged {len(coverage_dbs)} coverage files successfully.")

            # Parse merged coverage
            merged_coverage, total_coverage = QuestaSim.parse_coverage_report(merged_report_path)
            return CoverageResponse(True, 0, "Merged successfully", merged_coverage, total_coverage)
        except Exception as e:
            logging.error(f"Failed to generate merged coverage: {e}")
            return CoverageResponse(False, -1, f"Merge failed: {e}")

    def merge_and_parse_cross_run_coverage(
        self, design_name: str, work_dir: str, runs: int, max_iterations: int,
        batch_size: int, sim_runs: int, design_dir: str, use_store: bool
    ) -> CoverageResponse:
        """
        Merge QuestaSim coverage across all runs and parse the result.

        This method uses ArtifactPlan to systematically find all coverage database files,
        then merges and parses them.

        Args:
            design_name: Name of the design module
            work_dir: Working directory containing coverage files
            runs: Number of runs
            max_iterations: Maximum iterations per run
            batch_size: Batch size per iteration
            sim_runs: Number of simulation runs per testbench
            design_dir: Design directory path (not used, kept for signature compatibility)
            use_store: Whether using file store

        Returns:
            CoverageResponse: Response containing merged coverage data
        """
        try:
            # Collect all coverage database files using ArtifactPlan
            coverage_dbs = []
            for run_idx in range(runs):
                for iter_idx in range(max_iterations):
                    for batch_idx in range(batch_size):
                        tb_stem = f"tb_llm_{design_name}_{run_idx}_{iter_idx}_{batch_idx}"
                        artifact_plan = self.plan_artifacts(work_dir, tb_stem, sim_runs)

                        # Collect per-run coverage databases from the artifact plan
                        for cov_db in artifact_plan.per_run_coverage_dbs:
                            if os.path.exists(cov_db):
                                coverage_dbs.append(cov_db)

            if not coverage_dbs:
                logging.warning("No UCDB files found for merging coverage.")
                return CoverageResponse(False, -1, "No coverage files found")

            # Define output paths for merged coverage
            log_name = f"{work_dir}/merged_coverage_{design_name}"
            merged_ucdb_path = f"{log_name}.ucdb"
            merged_report_path = f"{log_name}_report.xml"

            # Merge coverage
            merge_output = self.generate_merged_coverage_report(
                self.design_unit,
                coverage_dbs,
                merged_ucdb_path,
                merged_report_path
            )

            logging.info(f"Merged {len(coverage_dbs)} coverage files successfully.")

            # Parse merged coverage
            merged_coverage, total_coverage = QuestaSim.parse_coverage_report(merged_report_path)
            return CoverageResponse(True, 0, "Merged successfully", merged_coverage, total_coverage)

        except Exception as e:
            logging.error(f"Failed to generate merged coverage: {e}")
            return CoverageResponse(False, -1, f"Merge failed: {e}")

    def format_coverage_summary(self, coverage: CoverageResponse) -> str:
        """
        Format QuestaSim coverage summary for LLM consumption.

        Args:
            coverage: Coverage response containing DU objects

        Returns:
            Formatted string with per-module coverage statistics
        """
        summary = f"Total Design Coverage: {coverage.total_coverage}%\n"

        # Defensive check: empty coverage list
        if not coverage.coverage_list:
            logging.warning("Coverage list is empty in format_coverage_summary")
            return summary + "\nNo coverage data available.\n"

        # Track type mismatches for debugging
        valid_entries = 0
        for inst in coverage.coverage_list:
            if isinstance(inst, DU):
                summary += (
                    f"File: {os.path.split(inst.path)[1]}\t"
                    f"Design Unit: {inst.du}\t"
                    f"Active: {inst.coverage['active']}\t"
                    f"Hits: {inst.coverage['hits']}\t"
                    f"Percent: {inst.coverage['percent']}%\n"
                )
                valid_entries += 1
            else:
                logging.warning(f"Unexpected type in coverage_list: {type(inst).__name__}. Expected DU.")

        if valid_entries == 0:
            logging.error("No valid DU objects found in coverage_list")
            return summary + "\nError: Coverage data contains no valid DU objects.\n"

        return summary

    def extract_coverage_feedback(
        self, coverage: CoverageResponse, top_design_module: str, work_dir: str
    ) -> str:
        """
        Extract QuestaSim coverage feedback for LLM.

        Selects a specific uncovered line in a module and provides the module
        context with the missed line marked inline.
        """
        import re

        # Defensive check: empty coverage list
        if not coverage.coverage_list:
            logging.warning("Coverage list is empty in extract_coverage_feedback")
            return "Warning: No coverage data available to extract feedback."

        # Verify coverage_list contains DU objects
        has_du = any(isinstance(item, DU) for item in coverage.coverage_list)
        if not has_du:
            logging.error(f"No DU objects in coverage_list. Found types: {[type(item).__name__ for item in coverage.coverage_list]}")
            return "Error: Coverage data does not contain expected DU objects."

        # Extract missed lines from DU coverage
        missed_lines = {}
        for inst in coverage.coverage_list:
            if isinstance(inst, DU):
                design_unit = inst.du
                for stmt in inst.coverage_details:
                    if stmt.get('hits') == '0':
                        line = int(str(stmt.get('ln')))
                        if design_unit not in missed_lines:
                            missed_lines[design_unit] = {"path": inst.path, "lines": []}
                        missed_lines[design_unit]["lines"].append(line)

        if not missed_lines:
            return "No missed lines found - coverage complete!"

        # Prioritize missed lines (control flow first)
        prioritized = self._prioritize_missed_lines(missed_lines)
        if not prioritized:
            return "No valid missed lines found."

        rand_du, missed_line, rand_du_filepath = prioritized[0]
        rand_du_filename = os.path.split(rand_du_filepath)[1]

        try:
            with open(rand_du_filepath, 'r', encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return f"Error: Could not open file {rand_du_filepath}."

        # Mark the missed line inline
        if 1 <= missed_line <= len(lines):
            lines[missed_line - 1] = lines[missed_line - 1].rstrip("\n") + "\t// This line was not covered\n"

        # Extract the module body
        start_line = end_line = None
        for i, line in enumerate(lines):
            if re.match(rf"\s*module\s+{rand_du}\b", line):
                start_line = i
            if re.match(r"\s*endmodule\b", line) and start_line is not None:
                end_line = i
                break

        module = ""
        if start_line is not None and end_line is not None:
            module = ''.join(lines[start_line:end_line])

        return f"""A missed line was detected in the module {rand_du}, located in {rand_du_filename}, specifically at line {missed_line}.

Important:
1. The test bench should ONLY target the top-level module {top_design_module}, even if the missed line exists in a submodule.
2. Ensure the test bench stimulates {top_design_module} in a way that exercises the missing coverage in {rand_du}.
3. Think about what signals you must drive on {top_design_module} to hit the coverage hole in {rand_du}.

Here is {rand_du} with the coverage hole marked:
{module}"""

    @staticmethod
    def _prioritize_missed_lines(missed_lines: dict) -> list:
        """Prioritize missed lines based on control flow importance."""
        prioritized = []

        for du, details in missed_lines.items():
            try:
                with open(details["path"], 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                for line_num in details["lines"]:
                    if 1 <= line_num <= len(lines):
                        code_line = lines[line_num - 1].strip()

                        # Check if line contains control flow keywords
                        if re.search(r'\b(if|case|while|for)\s*\(', code_line):
                            # High priority - insert at front
                            prioritized.insert(0, (du, line_num, details["path"]))
                        else:
                            # Normal priority - append at back
                            prioritized.append((du, line_num, details["path"]))

            except (FileNotFoundError, IndexError):
                continue

        return prioritized

