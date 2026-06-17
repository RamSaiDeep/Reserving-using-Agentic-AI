from models.triangle import Triangle
import json
with open('comauto_pos.csv', 'r') as f:
    text = f.read()
t = Triangle.from_csv(text)
ldfs = t.compute_ldfs()
print("Accident Years:", len(t.accident_years))
print("Dev Ages:", len(t.dev_ages))
print("LDFS:")
for l in ldfs:
    print(l['volumeWeighted'])
print("Diag:", t.get_latest_diagonal())
