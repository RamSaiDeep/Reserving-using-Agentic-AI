import pandas as pd
import json
import urllib.request
from models.triangle import Triangle

url = "https://raw.githubusercontent.com/casact/chainladder-python/main/chainladder/utils/data/comauto_pos.csv"
urllib.request.urlretrieve(url, "comauto_pos.csv")

with open("comauto_pos.csv", "r") as f:
    text = f.read()

t = Triangle.from_csv(text)
print("Detected format:", t._format)
print("AYs:", len(t.accident_years))
print("Dev Ages:", t.dev_ages)
print("Latest Diag:", t.get_latest_diagonal())
print("Total Paid:", sum(v for v in t.get_latest_diagonal() if v is not None))

ldfs = t.compute_ldfs()
print("LDFs:")
for i, l in enumerate(ldfs):
    print(f"{l['fromAge']}->{l['toAge']}: {l['volumeWeighted']}")
