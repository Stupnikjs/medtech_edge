import pandas as pd
import os 
from aliases import alias_map
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


RAW_DIR = "data/raw"
fda_ingestion_type = ("pma", "recall", "510k")

frames = []
for t in fda_ingestion_type:
    type_dir = os.path.join(RAW_DIR, t)
    if not os.path.isdir(type_dir):
        continue
    for year in os.listdir(type_dir):
        path = os.path.join(type_dir, year, "records.json")
        if os.path.exists(path):
            frames.append(pd.read_json(path))

df = pd.concat(frames, ignore_index=True)
print(df.groupby(df['applicant'].isna())['clearance_type'].value_counts())
df['applicant'] = df['applicant'].str.upper()

suffixes = r'\b(?:LTD|LLC|INC|CO|SE|BV|SA|US|BHD|PTY|SDN|GMBH|CORP|PLC|AG|NV)\.?\b'
df['applicant'] = df['applicant'].str.replace(suffixes, '', regex=True)
df['applicant'] = df['applicant'].str.strip(' .,')


df["applicant"] = df["applicant"].map(alias_map).fillna(df["applicant"])

print(df['applicant'].value_counts())



## grouper les noms qui on des similarité 
## systeme de token 