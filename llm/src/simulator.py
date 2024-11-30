class CoverageResponse:
    def __init__(self, success: bool, error_code: int, error_message: str = "", coverage_list: list[dict[str, str]] = [], total_coverage: int = 0):
        self.success = success
        # Error codes
        # 0: success -> ignore error message
        # 1: compile error
        # 2: simulation error
        # 3: simulation timeout
        # 4: JSON Decode error -> incomplete testbench
        self.error_code = error_code
        self.error_message = error_message
        self.coverage_list = coverage_list
        self.total_coverage = total_coverage

class Simulator():

    def __init__(self, simulator_path: str):
        self.simulator_path = simulator_path

    def run_sim(self) -> CoverageResponse:
        """Run the simulation - to be overridden by subclasses"""
        raise NotImplementedError("This method should be implemented by subclasses.")

    def merge_coverage(coverage_dbs: list[str]):
        """Merge the coverage of a list of provided coverage databases and return the coverage results"""
        raise NotImplementedError("This method should be implemented by subclasses.")