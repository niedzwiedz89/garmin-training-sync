#!/usr/bin/env python3
"""
Garmin Training Sync - Synchronize Garmin Connect activities to Google Sheets
"""

import os
import sys
import logging
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import gspread
from google.oauth2.service_account import Credentials
from garminconnect import Garmin
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
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class GarminSync:
    """Main class for synchronizing Garmin activities to Google Sheets"""

    def __init__(self):
        """Initialize Garmin and Google Sheets clients"""
        self.garmin_client = None
        self.sheet = None
        self.existing_activity_ids = set()

    def connect_garmin(self) -> bool:
        """
        Connect to Garmin Connect API

        Returns:
            bool: True if connection successful, False otherwise
        """
        logger.info("Connecting to Garmin Connect...")

        if not config.GARMIN_EMAIL or not config.GARMIN_PASSWORD:
            logger.error("Garmin credentials not found in environment variables")
            return False

        for attempt in range(config.MAX_RETRIES):
            try:
                self.garmin_client = Garmin(config.GARMIN_EMAIL, config.GARMIN_PASSWORD)
                self.garmin_client.login()
                logger.info("Successfully connected to Garmin Connect")
                return True
            except Exception as e:
                logger.warning(f"Garmin connection attempt {attempt + 1}/{config.MAX_RETRIES} failed: {e}")
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.RETRY_DELAY)
                else:
                    logger.error(f"Failed to connect to Garmin after {config.MAX_RETRIES} attempts")
                    return False

        return False

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
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

            # Create credentials object
            creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)

            # Authorize gspread client
            gc = gspread.authorize(creds)

            # Open or create the spreadsheet
            try:
                self.sheet = gc.open(config.GOOGLE_SHEET_NAME).sheet1
                logger.info(f"Opened existing spreadsheet: {config.GOOGLE_SHEET_NAME}")
            except gspread.SpreadsheetNotFound:
                logger.info(f"Creating new spreadsheet: {config.GOOGLE_SHEET_NAME}")
                spreadsheet = gc.create(config.GOOGLE_SHEET_NAME)
                self.sheet = spreadsheet.sheet1

                # Share with your email (optional - extract from credentials if needed)
                # spreadsheet.share('your-email@gmail.com', perm_type='user', role='writer')

            # Initialize headers if sheet is empty
            if not self.sheet.row_values(1):
                self.sheet.append_row(config.SHEET_HEADERS)
                logger.info("Initialized spreadsheet headers")

            # Load existing activity IDs to avoid duplicates
            self._load_existing_activities()

            logger.info("Successfully connected to Google Sheets")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in GOOGLE_SHEETS_CREDENTIALS: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            return False

    def _load_existing_activities(self):
        """Load existing activity IDs from the sheet to avoid duplicates"""
        try:
            # Get all values from the first column (activity_id)
            all_values = self.sheet.col_values(1)

            # Skip header and convert to set
            if len(all_values) > 1:
                self.existing_activity_ids = set(all_values[1:])
                logger.info(f"Loaded {len(self.existing_activity_ids)} existing activity IDs")
            else:
                self.existing_activity_ids = set()
                logger.info("No existing activities found in sheet")

        except Exception as e:
            logger.warning(f"Could not load existing activities: {e}")
            self.existing_activity_ids = set()

    def get_activities(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Get activities from Garmin Connect within date range

        Args:
            start_date: Start date for activity search
            end_date: End date for activity search

        Returns:
            List of activity dictionaries
        """
        logger.info(f"Fetching activities from {start_date.date()} to {end_date.date()}")

        activities = []

        for attempt in range(config.MAX_RETRIES):
            try:
                # Get activities from Garmin
                garmin_activities = self.garmin_client.get_activities_by_date(
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )

                logger.info(f"Found {len(garmin_activities)} activities")

                for activity in garmin_activities:
                    activity_id = str(activity.get('activityId', ''))

                    # Skip if already in sheet
                    if activity_id in self.existing_activity_ids:
                        logger.debug(f"Skipping duplicate activity: {activity_id}")
                        continue

                    activities.append(activity)

                logger.info(f"Filtered to {len(activities)} new activities")
                return activities

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{config.MAX_RETRIES} to fetch activities failed: {e}")
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.RETRY_DELAY)
                else:
                    logger.error(f"Failed to fetch activities after {config.MAX_RETRIES} attempts")
                    return []

        return []

    def process_activity(self, activity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single activity and extract metrics

        Args:
            activity: Raw activity data from Garmin

        Returns:
            Dictionary with processed metrics or None if processing failed
        """
        try:
            activity_id = str(activity.get('activityId', ''))

            if not activity_id:
                logger.warning("Activity without ID, skipping")
                return None

            # Initialize processed data with activity ID
            processed = {'activity_id': activity_id}

            # Extract basic info
            processed['activity_type'] = activity.get('activityType', {}).get('typeKey', '')

            # Parse and format date
            start_time_str = activity.get('startTimeLocal', '')
            if start_time_str:
                try:
                    # Parse ISO format: 2024-01-15 10:30:00
                    start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                    processed['date'] = start_time.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    logger.warning(f"Could not parse date {start_time_str}: {e}")
                    processed['date'] = start_time_str
            else:
                processed['date'] = ''

            # Activity name
            processed['title'] = activity.get('activityName', '')

            # Distance (convert from meters to km)
            distance_m = activity.get('distance')
            processed['distance_km'] = round(distance_m / 1000, 2) if distance_m else None

            # Duration (convert from seconds to minutes)
            duration_s = activity.get('duration')
            processed['duration_min'] = round(duration_s / 60, 2) if duration_s else None

            # Calories
            processed['calories'] = activity.get('calories')

            # Heart rate
            processed['avg_hr'] = activity.get('averageHR')
            processed['max_hr'] = activity.get('maxHR')

            # Pace/Speed (convert m/s to min/km for pace)
            avg_speed_ms = activity.get('averageSpeed')
            if avg_speed_ms and avg_speed_ms > 0:
                # Convert m/s to min/km: (1000 / speed_m_s) / 60
                pace_min_km = (1000 / avg_speed_ms) / 60
                processed['avg_pace'] = round(pace_min_km, 2)
            else:
                processed['avg_pace'] = None

            max_speed_ms = activity.get('maxSpeed')
            if max_speed_ms and max_speed_ms > 0:
                best_pace_min_km = (1000 / max_speed_ms) / 60
                processed['best_pace'] = round(best_pace_min_km, 2)
            else:
                processed['best_pace'] = None

            # Running-specific metrics
            processed['avg_run_cadence'] = activity.get('averageRunningCadenceInStepsPerMinute')
            processed['max_run_cadence'] = activity.get('maxRunningCadenceInStepsPerMinute')
            processed['avg_ground_contact_time_ms'] = activity.get('avgGroundContactTime')
            processed['avg_stride_length_m'] = activity.get('avgStrideLength')
            processed['avg_vertical_oscillation_cm'] = activity.get('avgVerticalOscillation')
            processed['avg_vertical_ratio'] = activity.get('avgVerticalRatio')
            processed['avg_gct_balance'] = activity.get('avgGctBalance')

            # Grade Adjusted Pace
            avg_gap_ms = activity.get('avgGradeAdjustedSpeed')
            if avg_gap_ms and avg_gap_ms > 0:
                gap_min_km = (1000 / avg_gap_ms) / 60
                processed['avg_gap'] = round(gap_min_km, 2)
            else:
                processed['avg_gap'] = None

            # Elevation
            processed['total_ascent_m'] = activity.get('elevationGain')
            processed['total_descent_m'] = activity.get('elevationLoss')

            # Training metrics
            processed['aerobic_te'] = activity.get('aerobicTrainingEffect')
            processed['training_stress_score'] = activity.get('trainingStressScore')

            # Steps
            processed['steps'] = activity.get('steps')

            # Respiration
            processed['avg_resp'] = activity.get('avgRespiration')
            processed['min_resp'] = activity.get('minRespiration')
            processed['max_resp'] = activity.get('maxRespiration')

            # Stress
            processed['avg_stress'] = activity.get('avgStress')
            processed['max_stress'] = activity.get('maxStress')

            # Power metrics
            processed['normalized_power'] = activity.get('normalizedPower')
            processed['avg_power'] = activity.get('avgPower')
            processed['max_power'] = activity.get('maxPower')

            # Time metrics (convert to minutes)
            moving_duration_s = activity.get('movingDuration')
            processed['moving_time_min'] = round(moving_duration_s / 60, 2) if moving_duration_s else None

            elapsed_duration_s = activity.get('elapsedDuration')
            processed['elapsed_time_min'] = round(elapsed_duration_s / 60, 2) if elapsed_duration_s else None

            return processed

        except Exception as e:
            logger.error(f"Error processing activity {activity.get('activityId', 'unknown')}: {e}")
            return None

    def write_to_sheets(self, activities: List[Dict[str, Any]]) -> int:
        """
        Write activities to Google Sheets

        Args:
            activities: List of processed activity dictionaries

        Returns:
            Number of activities successfully written
        """
        if not activities:
            logger.info("No activities to write")
            return 0

        written_count = 0

        for activity in activities:
            try:
                # Create row in the same order as SHEET_HEADERS
                row = []
                for header in config.SHEET_HEADERS:
                    value = activity.get(header)
                    # Convert None to empty string for Google Sheets
                    row.append(value if value is not None else '')

                # Insert row at position 2 (right after header) to keep newest at top
                self.sheet.insert_row(row, 2, value_input_option='USER_ENTERED')

                written_count += 1
                logger.info(f"Wrote activity: {activity.get('activity_id')} - {activity.get('title')}")

                # Add to existing IDs to prevent duplicate writes in same session
                self.existing_activity_ids.add(activity.get('activity_id'))

                # Small delay to avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to write activity {activity.get('activity_id')}: {e}")
                continue

        logger.info(f"Successfully wrote {written_count}/{len(activities)} activities to Google Sheets")
        return written_count

    def sync(self, days: int = None):
        """
        Main synchronization method

        Args:
            days: Number of days to sync (default: INITIAL_SYNC_DAYS for first run, 2 for subsequent)
        """
        logger.info("=" * 60)
        logger.info("Starting Garmin Training Sync")
        logger.info("=" * 60)

        # Connect to Garmin
        if not self.connect_garmin():
            logger.error("Could not connect to Garmin, aborting sync")
            return

        # Connect to Google Sheets
        if not self.connect_google_sheets():
            logger.error("Could not connect to Google Sheets, aborting sync")
            return

        # Determine date range
        end_date = datetime.now(config.TIMEZONE)

        if days is None:
            # If sheet is empty (no activities), use initial sync period
            days = config.INITIAL_SYNC_DAYS if not self.existing_activity_ids else 2

        start_date = end_date - timedelta(days=days)

        logger.info(f"Syncing last {days} days of activities")

        # Get activities
        activities = self.get_activities(start_date, end_date)

        if not activities:
            logger.info("No new activities to sync")
            return

        # Process activities
        processed_activities = []
        for activity in activities:
            processed = self.process_activity(activity)
            if processed:
                processed_activities.append(processed)

        logger.info(f"Successfully processed {len(processed_activities)}/{len(activities)} activities")

        # Sort activities by date (oldest first) so newest ends up on top when inserting
        processed_activities.sort(key=lambda x: x.get('date', ''), reverse=False)

        # Write to Google Sheets
        written = self.write_to_sheets(processed_activities)

        logger.info("=" * 60)
        logger.info(f"Sync completed: {written} new activities added")
        logger.info("=" * 60)


def main():
    """Main entry point"""
    try:
        syncer = GarminSync()
        syncer.sync()
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
