from xml.etree.ElementTree import Element

class DU:
    def __init__(self, path: str, du: str, coverage: dict[str, int | float], coverage_details: list[Element]) -> None:
        self.path: str
        self.du: str
        self.coverage: dict[str, int | float]
        self.coverage_details: list[Element]

        self.path = path
        self.du = du
        self.coverage = coverage
        self.coverage_details = coverage_details

class CoverageResponse:
    def __init__(self, success: bool = False, error_code: int = -1, error_message: str = "", coverage_list: list[DU] = [], total_coverage: float = 0):
        
        self.success: bool
        self.error_code: int
        self.error_message: str
        self.coverage_list: list[DU]
        self.total_coverage: float
        
        self.success = success
        # Error codes
        # -1: empty object
        # 0: success -> ignore error message
        # 1: compile error
        # 2: simulation error
        # 3: simulation timeout
        # 4: JSON Decode error -> incomplete testbench
        # 5: No $finish found -> LLM did not generate finish in test bench. Avoids running a test bench that will not finish
        self.error_code = error_code
        self.error_message = error_message
        self.coverage_list = coverage_list
        self.total_coverage = total_coverage

class Simulator():

    def __init__(self, simulator_path: str):
        self.simulator_path = simulator_path

    def run_sim(self, tb_path: str, data_point: dict[str, str | list[str]] | None, log_name: str) -> CoverageResponse:
        """Run the simulation - to be overridden by subclasses"""
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def generate_merged_coverage_report(self, du: str, coverage_dbs: list[str], log_name: str) -> str:
        """Generate merged coverage report - to be overridden by subclasses"""
        raise NotImplementedError("This method should be implemented by subclasses.")
    
    def merge_coverage(self) -> str:
        """Merge coverage - to be overridden by subclasses"""
        raise NotImplementedError("This method should be implemented by subclasses.")