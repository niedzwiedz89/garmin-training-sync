#!/usr/bin/env python3
"""
Fetch Training Data - Download all training data from Google Sheets for analysis
"""

import os
import sys
import json
import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from dotenv import load_dotenv

import config

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class TrainingDataFetcher:
    """Fetch training data from Google Sheets"""

    def __init__(self):
        """Initialize Google Sheets client"""
        self.sheet = None

    def connect_google_sheets(self) -> bool:
        """
        Connect to Google Sheets API

        Returns:
            bool: True if connection successful, False otherwise
        """
        logger.info("Connecting to Google Sheets...")

        try:
            # Get credentials from environment variable (JSON string)
            creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')

            if not creds_json:
                logger.error("Google Sheets credentials not found in environment variables")
                return False

            # Parse JSON credentials
            creds_dict = json.loads(creds_json)

            # Define the required scopes
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]

            # Create credentials object
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

            # Authorize gspread client
            gc = gspread.authorize(creds)

            # Open the spreadsheet
            try:
                self.sheet = gc.open(config.GOOGLE_SHEET_NAME).sheet1
                logger.info(f"Opened spreadsheet: {config.GOOGLE_SHEET_NAME}")
            except gspread.SpreadsheetNotFound:
                logger.error(f"Spreadsheet '{config.GOOGLE_SHEET_NAME}' not found")
                return False

            logger.info("Successfully connected to Google Sheets")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in GOOGLE_SHEETS_CREDENTIALS: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            return False

    def fetch_all_data(self) -> pd.DataFrame:
        """
        Fetch all training data from Google Sheets

        Returns:
            DataFrame with all training data
        """
        logger.info("Fetching all training data...")

        try:
            # Get all values from the sheet
            all_values = self.sheet.get_all_values()

            if not all_values:
                logger.warning("No data found in sheet")
                return pd.DataFrame()

            # First row is headers
            headers = all_values[0]
            data_rows = all_values[1:]

            if not data_rows:
                logger.warning("No training data found (only headers)")
                return pd.DataFrame()

            # Create DataFrame
            df = pd.DataFrame(data_rows, columns=headers)

            # Convert empty strings to None
            df = df.replace('', None)

            # Convert numeric columns
            numeric_columns = [
                'distance_km', 'duration_min', 'calories',
                'avg_hr', 'max_hr', 'avg_pace', 'best_pace',
                'avg_run_cadence', 'max_run_cadence',
                'avg_ground_contact_time_ms', 'avg_stride_length_m',
                'avg_vertical_oscillation_cm', 'avg_vertical_ratio',
                'avg_gap', 'total_ascent_m', 'total_descent_m',
                'aerobic_te', 'training_stress_score', 'steps',
                'avg_resp', 'min_resp', 'max_resp',
                'avg_stress', 'max_stress',
                'normalized_power', 'avg_power', 'max_power',
                'moving_time_min', 'elapsed_time_min'
            ]

            # Replace commas with dots in numeric columns (Polish locale fix)
            # Google Sheets in Polish locale uses comma as decimal separator
            for col in numeric_columns:
                if col in df.columns:
                    # Replace comma with dot for decimal numbers
                    df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
                    # Convert "None" string back to None
                    df[col] = df[col].replace('None', None)
                    # Convert to numeric
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Convert date column to datetime
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], errors='coerce')

            logger.info(f"Fetched {len(df)} training records")
            return df

        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return pd.DataFrame()

    def save_to_csv(self, df: pd.DataFrame, filename: str = None):
        """
        Save DataFrame to CSV file

        Args:
            df: DataFrame to save
            filename: Output filename (default: training_data_YYYYMMDD.csv)
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'training_data_{timestamp}.csv'

        try:
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"Data saved to: {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
            return None

    def print_summary(self, df: pd.DataFrame):
        """
        Print summary statistics of training data

        Args:
            df: DataFrame with training data
        """
        if df.empty:
            logger.warning("No data to summarize")
            return

        print("\n" + "=" * 70)
        print("TRAINING DATA SUMMARY")
        print("=" * 70)

        # Total records
        print(f"\nTotal activities: {len(df)}")

        # Date range
        if 'date' in df.columns and not df['date'].isna().all():
            min_date = df['date'].min()
            max_date = df['date'].max()
            print(f"Date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")

        # Activity types breakdown
        if 'activity_type' in df.columns:
            print(f"\nActivity types:")
            activity_counts = df['activity_type'].value_counts()
            for activity, count in activity_counts.items():
                print(f"   - {activity}: {count}")

        # Running statistics (if available)
        running_df = df[df['activity_type'].str.contains('running', case=False, na=False)]

        if not running_df.empty:
            print(f"\nRUNNING STATISTICS:")

            if 'distance_km' in running_df.columns:
                total_distance = running_df['distance_km'].sum()
                avg_distance = running_df['distance_km'].mean()
                print(f"   Total distance: {total_distance:.2f} km")
                print(f"   Average distance: {avg_distance:.2f} km per run")

            if 'duration_min' in running_df.columns:
                total_time = running_df['duration_min'].sum()
                avg_time = running_df['duration_min'].mean()
                print(f"   Total time: {total_time:.0f} minutes ({total_time/60:.1f} hours)")
                print(f"   Average time: {avg_time:.1f} minutes per run")

            if 'avg_pace' in running_df.columns:
                avg_pace = running_df['avg_pace'].mean()
                print(f"   Average pace: {avg_pace:.2f} min/km")

            if 'avg_hr' in running_df.columns:
                avg_hr = running_df['avg_hr'].mean()
                print(f"   Average heart rate: {avg_hr:.0f} bpm")

            if 'calories' in running_df.columns:
                total_calories = running_df['calories'].sum()
                print(f"   Total calories burned: {total_calories:.0f} kcal")

        # Recent activities
        if 'date' in df.columns and not df['date'].isna().all():
            print(f"\nLast 5 activities:")
            recent = df.nlargest(5, 'date')[['date', 'activity_type', 'title', 'distance_km', 'duration_min']]
            for idx, row in recent.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d') if pd.notna(row['date']) else 'N/A'
                distance_str = f"{row['distance_km']:.2f} km" if pd.notna(row['distance_km']) else 'N/A'
                duration_str = f"{row['duration_min']:.0f} min" if pd.notna(row['duration_min']) else 'N/A'
                print(f"   {date_str} | {row['activity_type']} | {row['title']} | {distance_str} | {duration_str}")

        print("\n" + "=" * 70)


def main():
    """Main entry point"""
    try:
        fetcher = TrainingDataFetcher()

        # Connect to Google Sheets
        if not fetcher.connect_google_sheets():
            logger.error("Could not connect to Google Sheets, aborting")
            sys.exit(1)

        # Fetch all data
        df = fetcher.fetch_all_data()

        if df.empty:
            logger.warning("No data to process")
            sys.exit(0)

        # Print summary
        fetcher.print_summary(df)

        # Save to CSV
        filename = fetcher.save_to_csv(df)

        if filename:
            print(f"\n[OK] Data saved to: {filename}")
            print(f"You can now analyze this file or share it for coaching feedback!")

    except KeyboardInterrupt:
        logger.info("Fetch interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
