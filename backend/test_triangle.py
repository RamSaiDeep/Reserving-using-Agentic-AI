import json
from reserving.core.triangle import Triangle
import pandas as pd

with open("../data/df_masked.csv", "r") as f:
    csv_text = f.read()

t = Triangle.from_csv(csv_text)
print("Detected Format:", t._format)
print("Accident Years (Count):", len(t.accident_years))
print("Accident Years Range:", min(t.accident_years), "to", max(t.accident_years))
print("Dev Ages:", t.dev_ages)
summary = t.get_summary()
print("Total Paid Claims:", summary['totalPaid'])
print("Has Premium Data:", summary['hasPremium'])
print("First Row Incurred Matrix:", t.incurred_matrix[0] if t.incurred_matrix else "Empty")
print("LDFs (First 3):", [f['volumeWeighted'] for f in t.compute_ldfs()[:3]])
