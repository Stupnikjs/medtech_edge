import pandas as pd
import os 


alias_map = {
    # Boston Scientific
    "BOSTON SCIENTIFIC CDIDINOSTIC TECHNOLOGIES": "BOSTON SCIENTIFIC",
    "BOSTON SCIENTIFIC RP": "BOSTON SCIENTIFIC",
    "BOSTON SCIENTIFIC RPORION": "BOSTON SCIENTIFIC",
    "BOSTON SCIENTIFIC CORP": "BOSTON SCIENTIFIC",
    "BOTT" : "BOTT",                                             
    "BOTT LORORIES":"BOTT",                                    
    "BOTT MEDIC":"BOTT",
        
    # Medtronic
    "MEDTRONIC SOFAMOR DANEK": "MEDTRONIC",
    "MEDTRONIC VASCULAR": "MEDTRONIC",
    
    # Johnson & Johnson / Ethicon
    "ETHICON ENDO SURGERY": "ETHICON",
    "ETHICON INC": "ETHICON",
    
    "PHILIPS HETH CE": "PHILIPS",
    "PHILIPS HETHCE (SUZHOU)": "PHILIPS",
    "PHILIPS MEDICSYSTEMS NEDERLD": "PHILIPS",
    "PHILIPS MEDICSYSTEMS NEDERLDS": "PHILIPS",
    "PHILIPS ULTROUND": "PHILIPS"
}


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

df['applicant'] = df['applicant'].str.upper()

suite_a_supprimer = r'(?:LTD|LLC|INC|CO|SE|B.V|A\S|US|BHD|PTY|SDN)\.?\s*'

df['applicant'] = df['applicant'].str.replace(suite_a_supprimer, '', regex=True)
df['applicant'] = df['applicant'].str.strip(" .")
df['applicant'] = df['applicant'].str.strip(" ,")

print(df['applicant'].value_counts().sort_index())
