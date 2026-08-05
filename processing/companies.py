import pandas as pd



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




df = pd.read_csv("./output/raw_510k_from_2020.csv")
df['applicant'] = df['applicant'].str.upper()

suite_a_supprimer = r'(?:LTD|LLC|INC|CO|SE|B.V|A\S|US|BHD|PTY|SDN)\.?\s*'

df['applicant'] = df['applicant'].str.replace(suite_a_supprimer, '', regex=True)
df['applicant'] = df['applicant'].str.strip(" .")
df['applicant'] = df['applicant'].str.strip(" ,")

print(df['applicant'].value_counts().sort_index()[500:550])
