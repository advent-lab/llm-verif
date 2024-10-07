import json
from pathlib import Path
from typing import Union

class Dataset:

    def __init__(self, dashboard_path: Union[str, Path]):

        with open(dashboard_path, 'r') as f:
            dashboard_content = f.read()

        decoder = json.JSONDecoder(strict=False)
        self.dataset = decoder.raw_decode(dashboard_content)[0]

    def get_data_point(self, design_name: str) -> Union[dict, None]:
        if design_name in self.dataset.keys():
            return self.dataset[design_name]
        else:
            return None

    def get_design_spec(self, design_name: str) -> Union[str, list, None]:
        if len(self.dataset[design_name]['spec']) == 0:
            return None
        elif len(self.dataset[design_name]['spec']) == 1:
            return self.dataset[design_name]['spec'][0]
        else:
            return self.dataset[design_name]['spec']

    def get_design(self, design_name: str) -> Union[str, list, None]:
        if len(self.dataset[design_name]['design']) == 0:
            return None
        elif len(self.dataset[design_name]['design']) == 1:
            return self.dataset[design_name]['design'][0]
        else:
            return self.dataset[design_name]['design']

    def get_design_context(self, design_name: str) -> Union[str, list, None]:
        if len(self.dataset[design_name]['design_context']) == 0:
            return None
        elif len(self.dataset[design_name]['design_context']) == 1:
            return self.dataset[design_name]['design_context'][0]
        else:
            return self.dataset[design_name]['design_context']

    def get_design_and_context(self, design_name: str) -> Union[str, list, None]:
        design = self.get_design(design_name)
        design_context = self.get_design_context(design_name)

        if not design and not design_context:
            return None
        elif not design:
            return design_context
        elif not design_context:
            return design
        else:
            return design + design_context




