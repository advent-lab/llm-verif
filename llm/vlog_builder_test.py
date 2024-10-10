from dashboard import Dataset
import questasim as qs

dataset = Dataset('/home/slowe8/Research/llm_verif_dataset/dashboard.json')

print(qs.vlog_builder('/home/slowe8/Research/llm_verif_dataset/data_points/chacha_top/tb_llm_chacha_top_0.v', dataset.get_data_point('chacha_top')))