import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "raw" / "usgs"

def load_usgs_file(filename):
    file_path = DATA_PATH / filename
    df = pd.read_csv(file_path, sep="\t")
    
    # Normalize column names
    df.columns = df.columns.str.lower()
    
    return df


def load_usgs_year(year):
    if year in [2018, 2019]:
        filename = f"EPest_county_estimates_{year}.txt"
        df = load_usgs_file(filename)
    elif year in [2013, 2014, 2015, 2016, 2017]:
        filename = "EPest_county_estimates_2013_2017_v2.txt"
        df = load_usgs_file(filename)
        df = df[df["year"] == year]
    else:
        raise ValueError("Year not available in current files.")
    
    return df