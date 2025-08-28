import pandas as pd
import glob
import os

# === CONFIGURATION ===
input_dir = "./results"  # directory containing CSVs (now with subdirs)
output_file = "combined.csv"  # output file name

# === COMBINE CSVs ===
# Use ** to search recursively in subdirectories
all_csv_files = glob.glob(os.path.join(input_dir, "**", "*.csv"), recursive=True)

if not all_csv_files:
    print("No CSV files found in the directory or subdirectories.")
else:
    df_list = []
    for file in all_csv_files:
        df = pd.read_csv(file)
        df["source_file"] = os.path.relpath(file, input_dir)  # optionally track relative path
        df_list.append(df)

    combined_df = pd.concat(df_list, ignore_index=True)
    combined_df.to_csv(output_file, index=False)
    print(f"Combined {len(all_csv_files)} files into {output_file}")


