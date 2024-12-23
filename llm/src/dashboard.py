import json
from pathlib import Path
from typing import Union

class Dataset:

    def __init__(self, dashboard_path: Union[str, Path]):

        with open(dashboard_path, 'r') as f:
            dashboard_content = f.read()

        self.base_dir = str(Path(dashboard_path).parents[0]) + '/data_points'

        decoder = json.JSONDecoder(strict=False)
        self.dataset = decoder.raw_decode(dashboard_content)[0]
        self.replace_base_dir()

    def get_data_point(self, design_name: str) -> Union[dict, None]:
        if design_name in self.dataset.keys():
            return self.dataset[design_name]
        else:
            return None

    def get_design_spec(self, design_name: str) -> Union[str, list, None]:
        return self.check_list(self.dataset[design_name], 'spec')

    def get_design(self, design_name: str) -> Union[str, list, None]:
        return self.check_list(self.dataset[design_name], 'design')

    def get_design_context(self, design_name: str) -> Union[str, list, None]:
        return self.check_list(self.dataset[design_name], 'design_context')

    def get_design_and_context(self, design_name: str) -> Union[list, None]:
        design = self.get_design(design_name)
        design_context = self.get_design_context(design_name)

        # Ensure both design and design_context are lists of strings
        if isinstance(design, str):
            design = [design]  # Cast string to list
        if isinstance(design_context, str):
            design_context = [design_context]  # Cast string to list

        if not design and not design_context:
            return None
        elif not design:
            return design_context
        elif not design_context:
            return design
        else:
            return design_context + design

    def replace_base_dir(self):
        for tkey in self.dataset.keys():
            for dkey in self.dataset[tkey].keys():
                if isinstance(self.dataset[tkey][dkey], str):
                    self.dataset[tkey][dkey] = self.dataset[tkey][dkey].replace('$(BASE_DIR)', self.base_dir)
                elif isinstance(self.dataset[tkey][dkey], list):
                    for i in range(len(self.dataset[tkey][dkey])):
                        self.dataset[tkey][dkey][i] = self.dataset[tkey][dkey][i].replace('$(BASE_DIR)', self.base_dir)

    def check_list(self, dlist: Union[str, list], key: str) -> list:
        if len(dlist[key]) == 0:
            return None
        elif len(dlist[key]) == 1:
            return dlist[key][0]
        else:
            return dlist[key]

        




