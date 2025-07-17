import questasim as qs
from dashboard import Dataset
import os

dataset = Dataset('../dashboard.json')

data_point = dataset.get_data_point('chacha_core')

directory = '/scratch/slowe8/chacha_core_method1_runs/generations'

for filename in os.listdir(directory):
    print(qs.run_questasim('/packages/apps/fpga/Questa/questa_fe/bin', os.path.join(directory, filename), data_point, filename.split('.')[0]).error_code)