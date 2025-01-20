class CoverageResponse:
    def __init__(self, success: bool, error_code: int, error_message: str = "", coverage_list: list[dict[str, str]] = [], total_coverage: float = 0):
        
        self.success: bool
        self.error_code: int
        self.error_message: str
        self.coverage_list: list[dict[str, str]]
        self.total_coverage: float
        
        self.success = success
        # Error codes
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

    def run_sim(self) -> CoverageResponse:
        """Run the simulation - to be overridden by subclasses"""
        raise NotImplementedError("This method should be implemented by subclasses.")