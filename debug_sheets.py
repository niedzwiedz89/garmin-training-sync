#!/usr/bin/env python3
"""Debug script to check Google Sheets data"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import config

load_dotenv()

# Connect to Google Sheets
creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
creds_dict = json.loads(creds_json)
scopes = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
gc = gspread.authorize(creds)
sheet = gc.open(config.GOOGLE_SHEET_NAME).sheet1

# Get first 5 rows
print("First 5 rows from Google Sheets:")
print("=" * 100)

rows = sheet.get_all_values()[:6]  # Header + 5 data rows

for i, row in enumerate(rows):
    if i == 0:
        print(f"Row {i} (HEADER):")
        for j, cell in enumerate(row):
            print(f"  Col {j}: '{cell}'")
    else:
        print(f"\nRow {i} (DATA):")
        # Show only important columns
        print(f"  activity_id: '{row[0]}'")
        print(f"  activity_type: '{row[1]}'")
        print(f"  title: '{row[3]}'")
        print(f"  distance_km (col 4): '{row[4]}'")
        print(f"  duration_min (col 5): '{row[5]}'")
        print(f"  calories (col 6): '{row[6]}'")
