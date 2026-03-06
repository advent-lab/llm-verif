import json
import os
import argparse
from pathlib import Path
from typing import Dict, List, Union

class LOCCalculator:

    def __init__(self, dashboard_path: str, base_dir: str):
        self.dashboard_path = dashboard_path
        self.base_dir = base_dir
        self.dashboard = self._load_dashboard()

    def _load_dashboard(self) -> Dict:
        with open(self.dashboard_path, 'r') as f:
            return json.load(f)
        
    def _resolve_path(self, path_str: str) -> str:
        resolved = path_str.replace("$(BASE_DIR)", self.base_dir)
        return str(Path(resolved))
    
    def _normalize_file_list(self, value: Union[str, List, None]) -> List[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return value
        return []
    
    def _count_lines_in_file(self, filepath: str) -> int:
        """Count actual lines of code, excluding comments and blank lines"""
        if not os.path.exists(filepath):
            return 0
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            code_lines = 0
            in_multiline_comment = False
            
            for line in lines:
                stripped = line.strip()
                
                # Skip blank lines
                if not stripped:
                    continue
                
                # Handle multi-line comments
                if '/*' in stripped:
                    in_multiline_comment = True
                
                # Check if this line ends a multi-line comment
                if '*/' in stripped:
                    in_multiline_comment = False
                    # If */ is on the same line as /*, or if there's code after */, count it
                    after_comment = stripped.split('*/', 1)[-1].strip()
                    if after_comment and not after_comment.startswith('//'):
                        code_lines += 1
                    continue
                
                # Skip lines inside multi-line comments
                if in_multiline_comment:
                    continue
                
                # Skip single-line comment-only lines
                if stripped.startswith('//'):
                    continue
                
                # Count this line as code
                code_lines += 1
            
            return code_lines
        except Exception as e:
            return 0
        
    def count_loc_for_design(self, design_name: str, include_categories: List[str] = None) -> Dict:
        
        if include_categories is None:
            include_categories = ['design', 'design_context']

        if design_name not in self.dashboard:
            return {"error": f"Design '{design_name}' not found", "total": 0, "files": {}}
        
        design_data = self.dashboard[design_name]
        loc_breakdown = {}
        file_details = {}
        total_loc = 0

        for category in include_categories:
            files = self._normalize_file_list(design_data.get(category))
            category_loc = 0
            category_files = []

            for file_path in files:
                resolved_path = self._resolve_path(file_path)
                loc = self._count_lines_in_file(resolved_path)
                category_loc += loc
                if loc > 0:
                    category_files.append((Path(resolved_path).name, loc))

            loc_breakdown[category] = category_loc
            file_details[category] = category_files
            total_loc += category_loc

        loc_breakdown['total'] = total_loc
        loc_breakdown['files'] = file_details
        return loc_breakdown

    def count_all_designs(self, include_categories: List[str] = None) -> Dict:
        if include_categories is None:
            include_categories = ['design', 'design_context']
        results = {}
        for design_name in self.dashboard.keys():
            results[design_name] = self.count_loc_for_design(design_name, include_categories)
        return results

    def print_summary_report(self, results: Dict, sort_by: str = 'total', verbose: bool = False):
        if sort_by == 'total':
            sorted_designs = sorted(results.items(), key=lambda x: x[1]['total'], reverse=True)
        elif sort_by == 'name':
            sorted_designs = sorted(results.items())
        else:
            sorted_designs = results.items()

        print("\nLOC count utilizing dashboard.json\n")

        total_loc = 0
        for design_name, loc_data in sorted_designs:
            loc = loc_data['total']
            total_loc += loc
            print("-"*70)
            print(f"{design_name}: {loc:,}")
            
            # Show files included in count (if verbose)
            if verbose:
                files_data = loc_data.get('files', {})
                for category, files in files_data.items():
                    if files:
                        print(f"  [{category}]")
                        for filename, file_loc in files:
                            print(f"    {filename}: {file_loc:,}")

        print("\n" + "="*70)
        print(f"Total: {total_loc:,} LOC across {len(results)} designs")
        print("="*70 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calculate LOC for hardware designs')
    parser.add_argument('--categories', nargs='+', 
                        default=['design', 'design_context'],
                        help='Categories to include (default: design design_context)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show individual files included in LOC count')
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    base_dir = os.path.join(project_dir, "data")
    dashboard_path = os.path.join(project_dir, "dashboard.json")

    calc = LOCCalculator(dashboard_path, base_dir)
    results = calc.count_all_designs(args.categories)
    calc.print_summary_report(results, sort_by='total', verbose=args.verbose)
