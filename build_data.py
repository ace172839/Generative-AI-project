import pandas as pd
import re
import json

# Define input and output file names
INPUT_CSV = 'house.csv'
OUTPUT_JSON = 'data.json'

def extract_district(addr):
    """
    Extracts the administrative district from a given address.
    Skips the first 3 characters (city) and captures up to the district/township marker.
    """
    if pd.isna(addr):
        return ""
    
    addr = str(addr)
    match = re.search(r'^.{3}(.+?[區鄉鎮市])', addr)
    
    if match:
        return match.group(1)
    else:
        return ""

def process_csv_to_json(input_file, output_file):
    """
    Reads a CSV file, processes it to add a district column,
    and saves the result as a JSON file.
    """
    print(f"Reading data from {input_file}...")
    try:
        df = pd.read_csv(input_file, encoding='utf-8')
    except UnicodeDecodeError:
        print("UTF-8 decoding failed, trying big5...")
        df = pd.read_csv(input_file, encoding='big5')

    print(f"Successfully read {len(df)} records. Processing...")

    # Assume the address column is named '地址'
    if '地址' in df.columns:
        df['行政區'] = df['地址'].apply(extract_district)
        print("'行政區' column created successfully.")
    else:
        print("Warning: '地址' column not found. Skipping district extraction.")

    # Convert DataFrame to a list of dictionaries
    data = df.to_dict(orient='records')

    # Save to JSON
    print(f"Saving processed data to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"Data processing complete. {output_file} has been created.")

if __name__ == '__main__':
    process_csv_to_json(INPUT_CSV, OUTPUT_JSON)
