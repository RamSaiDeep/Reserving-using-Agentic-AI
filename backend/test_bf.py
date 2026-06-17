from models.triangle import Triangle
from models.methods import METHODS
import json
with open('comauto_pos.csv', 'r') as f:
    text = f.read()
t = Triangle.from_csv(text)
print("Premiums:", t.premiums)
print("Latest Diag:", t.get_latest_diagonal())
ldfs = [f['volumeWeighted'] for f in t.compute_ldfs()[:-1]]
ldfs.append(1.0)
print("LDFs:", ldfs)
bf = METHODS['BF']()
bf.fit(t, {'aprioriLossRatio': 0.65}, ldfs)
print("Total IBNR:", bf.get_total_ibnr())
