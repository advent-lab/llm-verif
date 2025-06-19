from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from dashboard import Dataset
from util import extract_verilog_module_header
from questasim import QuestaSim

import os
import sys
from pathlib import Path
import subprocess

# Add the project root to the PYTHONPATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Set the environment variable
os.environ["LM_LICENSE_FILE"] = "27006@en4228283l.scai.dhcp.asu.edu"

load_dotenv("../.env")

from graph_def import graph

dataset = Dataset("/home/local/ASURITE/slowe8/thesis/llm_verif_dataset/dashboard.json")
sha1_top = dataset.get_data_point("sha1_top")

module_header = extract_verilog_module_header(str(sha1_top["design"][0]))
with open(str(sha1_top["spec"][0]), 'r') as f:
    design_specification = f.read()


initial_state = { 
  "design_spec": design_specification, 
  "module_header": module_header,
  "testbench_path": "tb_llm.v",
  "test_plan": "",
  "test_bench": "",
  "coverage": {},
  "improvement_directive": "",
  "data_point": sha1_top,
  "log_name": "sha1_top",
  "simulator": QuestaSim("/mnt/vault0/tools/Intel/intelFPGA_pro/23.4/questa_fe/bin"),
}

final_state = graph.invoke(initial_state)

print("Final State:", final_state)
for k, v in final_state.items():
    print(f"{k}: {v}")