import csv
from pathlib import Path

path = Path('/home/ubuntu/ai-product-intelligence/backend/data/evaluation/Unihack_SampleDataset-Input.csv')
with path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print('headers', reader.fieldnames)
    for row in reader:
        if row.get('Mfg_Part_Num') in {'PDSH4816AF', 'WDTS7024RZ'}:
            print('id', row.get('Mfg_Part_Num'))
            print({k: v for k, v in row.items() if v not in (None, '')})

# Also inspect the uploaded copy if the evaluation copy differs.
for candidate in [
    Path('/home/ubuntu/upload/Unihack_SampleDataset-Input.csv'),
    Path('/home/ubuntu/ai-product-intelligence/backend/data/uploads/Unihack_ Sample Dataset - Input.csv'),
]:
    if not candidate.exists():
        continue
    print('candidate', candidate)
    with candidate.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('Mfg_Part_Num') in {'PDSH4816AF', 'WDTS7024RZ'}:
                print({k: v for k, v in row.items() if v not in (None, '')})
            
