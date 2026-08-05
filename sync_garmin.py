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
        self.workout_cache = {}

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
                # GARMINTOKENS = tokeny podane wprost (sekret w CI), inaczej katalog w profilu
                tokenstore = os.getenv('GARMINTOKENS') or os.path.join(
                    os.path.expanduser("~"), ".garth_sync_garmin")
                inline_tokens = len(tokenstore) > 512
                had_tokens = inline_tokens or os.path.exists(
                    os.path.join(tokenstore, 'garmin_tokens.json'))

                self.garmin_client = Garmin(config.GARMIN_EMAIL, config.GARMIN_PASSWORD)
                try:
                    self.garmin_client.login(tokenstore)
                    logger.info(
                        "Successfully connected to Garmin Connect (%s)",
                        "stored tokens" if had_tokens else "credential login, tokens saved")
                    return True
                except Exception:
                    logger.info("Stored tokens missing or expired, logging in with credentials...")
                    self.garmin_client.login()
                    if not inline_tokens:
                        self.garmin_client.client.dump(tokenstore)
                    logger.info("Successfully connected to Garmin Connect and cached tokens")
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

            headers = self.sheet.row_values(1)
            if not headers:
                self.sheet.append_row(config.SHEET_HEADERS)
                logger.info("Initialized spreadsheet headers")
            elif headers != config.SHEET_HEADERS[:len(headers)] or len(headers) < len(config.SHEET_HEADERS):
                # kolejnosc kolumn musi odpowiadac SHEET_HEADERS - wiersze sa budowane po indeksie
                if headers == config.SHEET_HEADERS[:len(headers)]:
                    self.sheet.update(
                        [config.SHEET_HEADERS],
                        f"A1:{gspread.utils.rowcol_to_a1(1, len(config.SHEET_HEADERS))}")
                    logger.info(f"Extended headers to {len(config.SHEET_HEADERS)} columns")
                else:
                    logger.error("Sheet headers do not match SHEET_HEADERS - aborting to avoid "
                                 "writing values into wrong columns")
                    return False

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

    @staticmethod
    def _pace(speed_mps: Optional[float]) -> Optional[str]:
        """m/s -> 'mm:ss' na kilometr"""
        if not speed_mps or speed_mps <= 0:
            return None
        minutes, seconds = divmod(int(round(1000 / speed_mps)), 60)
        return f"{minutes}:{seconds:02d}"

    def _workout_plan(self, workout_id: Any) -> Optional[Dict[str, Any]]:
        """Cele z definicji workoutu: ile powtorzen, jak dlugie, w jakim tempie"""
        if not workout_id:
            return None
        if workout_id in self.workout_cache:
            return self.workout_cache[workout_id]

        plan = None
        try:
            workout = self.garmin_client.get_workout_by_id(workout_id)
            for segment in workout.get('workoutSegments', []):
                for step in segment.get('workoutSteps', []):
                    if step.get('type') != 'RepeatGroupDTO':
                        continue
                    for sub in step.get('workoutSteps', []):
                        if (sub.get('stepType') or {}).get('stepTypeKey') != 'interval':
                            continue
                        cond = (sub.get('endCondition') or {}).get('conditionTypeKey')
                        value = sub.get('endConditionValue')
                        t1, t2 = sub.get('targetValueOne'), sub.get('targetValueTwo')
                        plan = {
                            'powtorzen': step.get('numberOfIterations'),
                            'krok': (f"{int(value)}s" if cond == 'time'
                                     else f"{int(value)}m" if value else None),
                            'cel': (f"{self._pace(max(t1, t2))}-{self._pace(min(t1, t2))}"
                                    if t1 and t2 else None),
                        }
        except Exception as e:
            logger.debug(f"Could not read workout {workout_id}: {e}")

        self.workout_cache[workout_id] = plan
        return plan

    def build_quality(self, activity: Dict[str, Any]) -> Optional[str]:
        """
        Profil jakosciowy sesji jako JSON. Pola darmowe ida z podsumowania aktywnosci,
        odcinki i cele dociagane tylko dla sesji ze struktura (1-2 dodatkowe zapytania).
        """
        try:
            quality: Dict[str, Any] = {
                'label': activity.get('trainingEffectLabel'),
                'te': {'aer': activity.get('aerobicTrainingEffect'),
                       'ana': activity.get('anaerobicTrainingEffect')},
            }
            load = activity.get('activityTrainingLoad')
            if load:
                quality['load'] = round(load, 1)

            summaries = {s.get('splitType'): s for s in (activity.get('splitSummaries') or [])}
            interval = summaries.get('INTERVAL_ACTIVE')
            # pojedynczy INTERVAL_ACTIVE to zwykle wybieganie z autolapami, nie sesja ze struktura
            if not interval or (interval.get('noOfSplits') or 0) < 2:
                return json.dumps(quality, ensure_ascii=False)

            quality['praca'] = {
                'km': round((interval.get('distance') or 0) / 1000, 2),
                'tempo': self._pace(interval.get('averageSpeed')),
            }

            laps = (self.garmin_client.get_activity_splits(activity['activityId']) or {}).get('lapDTOs', [])
            robocze = [l for l in laps
                       if l.get('intensityType') == 'ACTIVE' and (l.get('distance') or 0) > 50]
            przerwy = [l for l in laps if l.get('intensityType') in ('RECOVERY', 'REST')]

            if robocze:
                tempa_s = [1000 / l['averageSpeed'] for l in robocze if l.get('averageSpeed')]
                # HR i kadencja liczone z okrazen - podsumowanie z listy aktywnosci ich nie zawiera
                czas = sum(l.get('duration') or 0 for l in robocze) or 1

                def srednia(pole):
                    wazona = sum((l.get(pole) or 0) * (l.get('duration') or 0) for l in robocze)
                    return round(wazona / czas) or None

                quality.setdefault('praca', {})
                quality['praca'].update({
                    'wykonane': len(robocze),
                    'tempa': [self._pace(l.get('averageSpeed')) for l in robocze],
                    'hr': srednia('averageHR'),
                    'kadencja': srednia('averageRunCadence'),
                    'gct': srednia('groundContactTime'),
                })
                if tempa_s:
                    quality['fade_s'] = round(tempa_s[-1] - tempa_s[0])
                    quality['rozrzut_s'] = round(max(tempa_s) - min(tempa_s))
                if przerwy:
                    quality['przerwa_s'] = round(sum(l.get('duration') or 0 for l in przerwy) / len(przerwy))

                # score bez zdefiniowanego celu zawsze wynosi 100 - wtedy nie niesie informacji
                oceny = [l['directWorkoutComplianceScore'] for l in robocze
                         if l.get('directWorkoutComplianceScore') is not None]
                plan = self._workout_plan(activity.get('workoutId'))
                if plan:
                    quality['plan'] = plan
                    if plan.get('powtorzen'):
                        quality['kompletnosc'] = round(100 * len(robocze) / plan['powtorzen'])
                if oceny and plan and plan.get('cel'):
                    quality['zgodnosc'] = {'srednia': round(sum(oceny) / len(oceny)),
                                           'per_powt': [round(o) for o in oceny]}

            quality['opis'] = self._opis(quality)
            return json.dumps(quality, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"Could not build quality profile for {activity.get('activityId')}: {e}")
            return None

    @staticmethod
    def _opis(q: Dict[str, Any]) -> str:
        """Jednolinijkowe streszczenie sesji dla czlowieka"""
        praca, plan = q.get('praca') or {}, q.get('plan') or {}
        czesci = []
        if praca.get('wykonane'):
            ile = (f"{praca['wykonane']}/{plan['powtorzen']}" if plan.get('powtorzen')
                   else str(praca['wykonane']))
            czesci.append(f"{ile} x {plan.get('krok') or '?'} @{praca.get('tempo') or '?'}")
        elif praca.get('km'):
            czesci.append(f"praca {praca['km']} km @{praca.get('tempo') or '?'}")
        if plan.get('cel'):
            czesci.append(f"cel {plan['cel']}")
        if q.get('przerwa_s'):
            czesci.append(f"p.{q['przerwa_s']}s")
        if q.get('fade_s') is not None:
            czesci.append(f"fade {q['fade_s']:+d}s")
        if q.get('zgodnosc'):
            czesci.append(f"zgodnosc {q['zgodnosc']['srednia']}%")
        elif praca.get('wykonane'):
            czesci.append("zgodnosc - (brak celu tempa)")
        return " | ".join(czesci) or (q.get('label') or '')

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

            processed['te_label'] = activity.get('trainingEffectLabel')
            processed['ana_te'] = activity.get('anaerobicTrainingEffect')
            training_load = activity.get('activityTrainingLoad')
            processed['training_load'] = round(training_load, 1) if training_load else None
            processed['quality_json'] = self.build_quality(activity)

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

        rows_to_insert = []

        for activity in activities:
            try:
                # Create row in the same order as SHEET_HEADERS
                row = []
                for header in config.SHEET_HEADERS:
                    value = activity.get(header)
                    # Convert None to empty string for Google Sheets
                    row.append(value if value is not None else '')

                rows_to_insert.append(row)
                logger.info(f"Prepared activity: {activity.get('activity_id')} - {activity.get('title')}")

                # Add to existing IDs to prevent duplicate writes in same session
                self.existing_activity_ids.add(activity.get('activity_id'))
                written_count += 1

            except Exception as e:
                logger.error(f"Failed to process activity {activity.get('activity_id')}: {e}")
                continue

        if rows_to_insert:
            try:
                # Insert all rows at once at position 2 (batch write avoids rate limiting)
                self.sheet.insert_rows(rows_to_insert, 2, value_input_option='USER_ENTERED')
                logger.info(f"Successfully batch wrote {written_count}/{len(activities)} activities to Google Sheets")
            except Exception as e:
                logger.error(f"Failed to batch write activities: {e}")
                return 0

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

        # Sort activities by date (newest first) so they are in correct order for batch insert at row 2
        processed_activities.sort(key=lambda x: x.get('date', ''), reverse=True)

        # Write to Google Sheets
        written = self.write_to_sheets(processed_activities)

        logger.info("=" * 60)
        logger.info(f"Sync completed: {written} new activities added")
        logger.info("=" * 60)


def main():
    """Main entry point"""
    try:
        days = None
        if len(sys.argv) > 1:
            try:
                days = int(sys.argv[1])
            except ValueError:
                logger.error("The 'days' argument must be an integer.")
                sys.exit(1)
                
        syncer = GarminSync()
        syncer.sync(days=days)
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
