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
print(df.groupby(df['applicant'].isna())['clearance_type'].value_counts())
df['applicant'] = df['applicant'].str.upper()

suffixes = r'\b(?:LTD|LLC|INC|CO|SE|BV|SA|US|BHD|PTY|SDN|GMBH|CORP|PLC|AG|NV)\.?\b'
df['applicant'] = df['applicant'].str.replace(suffixes, '', regex=True)
df['applicant'] = df['applicant'].str.strip(' .,')


print(df['applicant'].value_counts().sort_index())


## grouper les noms qui on des similarité 
## systeme de token 