from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer
import os

os.environ["HF_HOME"] = f"/scratch/{os.environ['USER']}/.cache"

model_path = "meta-llama/Llama-3.3-70B-Instruct"
quant_path = f"{os.environ['HF_HOME']}/Llama-3.3-70B-Instruct-awq"
quant_config = {
    "zero_point": True,
    "q_group_size": 128,
    "w_bit": 4,
    "version": "GEMM"
}

# Load model
model = AutoAWQForCausalLM.from_pretrained(
    model_path, **{"low_cpu_mem_usage": True, "use_cache": False}
)
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

# Quantize
model.quantize(tokenizer, quant_config=quant_config)

# Save quantized model
model.save_quantized(quant_path)
tokenizer.save_quantized(quant_path)

print(f"Model is quantized and saved at {quant_path}")

