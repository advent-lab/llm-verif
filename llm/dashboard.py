import json
from pathlib import Path
from typing import Union

class Dashboard:

    def __init__(self, dashboard_path: Union[str, Path]):

        with open(dashboard_path, 'r') as f:
            dashboard_content = f.read()

        decoder = json.JSONDecoder(strict=False)
        self.dataset = decoder.raw_decode(dashboard_content)[0]

    def get_design(self, design_name: str) -> Union[dict, None]:
        if design_name in self.dataset.keys():
            return self.dataset[design_name]
        else:
            return None

