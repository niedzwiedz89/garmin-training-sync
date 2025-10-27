"""
Configuration file for Garmin Training Sync
"""

import os
from datetime import datetime
import pytz

# Timezone configuration
TIMEZONE = pytz.timezone('Europe/Warsaw')

# Google Sheets configuration
GOOGLE_SHEET_NAME = 'garmin_trainings'
GOOGLE_SHEET_PATH = r'G:\Mój dysk\Bieganie\garmin_trainings.xlsx'

# Garmin configuration
GARMIN_EMAIL = os.getenv('GARMIN_EMAIL')
GARMIN_PASSWORD = os.getenv('GARMIN_PASSWORD')

# Initial sync period (days)
INITIAL_SYNC_DAYS = 30

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
API_TIMEOUT = 30  # seconds

# Logging configuration
LOG_FILE = 'sync_garmin.log'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Metrics to collect (Priority 1 - Basic)
BASIC_METRICS = [
    'activityType',
    'startTimeLocal',
    'activityName',
    'distance',
    'duration',
    'calories',
    'averageHR',
    'maxHR',
    'averageSpeed',
    'maxSpeed',
]

# Metrics to collect (Priority 2 - Running Advanced)
RUNNING_METRICS = [
    'averageRunningCadenceInStepsPerMinute',
    'maxRunningCadenceInStepsPerMinute',
    'avgGroundContactTime',
    'avgStrideLength',
    'avgVerticalOscillation',
    'avgVerticalRatio',
    'avgGctBalance',
    'avgGradeAdjustedSpeed',
    'elevationGain',
    'elevationLoss',
]

# Metrics to collect (Priority 3 - Additional)
ADDITIONAL_METRICS = [
    'aerobicTrainingEffect',
    'trainingStressScore',
    'steps',
    'avgRespiration',
    'minRespiration',
    'maxRespiration',
    'avgStress',
    'maxStress',
    'normalizedPower',
    'avgPower',
    'maxPower',
    'movingDuration',
    'elapsedDuration',
]

# All metrics combined
ALL_METRICS = BASIC_METRICS + RUNNING_METRICS + ADDITIONAL_METRICS

# Column names for Google Sheets (friendly names)
COLUMN_MAPPING = {
    'activityType': 'activity_type',
    'startTimeLocal': 'date',
    'activityName': 'title',
    'distance': 'distance_km',
    'duration': 'duration_min',
    'calories': 'calories',
    'averageHR': 'avg_hr',
    'maxHR': 'max_hr',
    'averageSpeed': 'avg_pace',
    'maxSpeed': 'best_pace',
    'averageRunningCadenceInStepsPerMinute': 'avg_run_cadence',
    'maxRunningCadenceInStepsPerMinute': 'max_run_cadence',
    'avgGroundContactTime': 'avg_ground_contact_time_ms',
    'avgStrideLength': 'avg_stride_length_m',
    'avgVerticalOscillation': 'avg_vertical_oscillation_cm',
    'avgVerticalRatio': 'avg_vertical_ratio',
    'avgGctBalance': 'avg_gct_balance',
    'avgGradeAdjustedSpeed': 'avg_gap',
    'elevationGain': 'total_ascent_m',
    'elevationLoss': 'total_descent_m',
    'aerobicTrainingEffect': 'aerobic_te',
    'trainingStressScore': 'training_stress_score',
    'steps': 'steps',
    'avgRespiration': 'avg_resp',
    'minRespiration': 'min_resp',
    'maxRespiration': 'max_resp',
    'avgStress': 'avg_stress',
    'maxStress': 'max_stress',
    'normalizedPower': 'normalized_power',
    'avgPower': 'avg_power',
    'maxPower': 'max_power',
    'movingDuration': 'moving_time_min',
    'elapsedDuration': 'elapsed_time_min',
}

# Headers for Google Sheets
SHEET_HEADERS = [
    'activity_id',
    'activity_type',
    'date',
    'title',
    'distance_km',
    'duration_min',
    'calories',
    'avg_hr',
    'max_hr',
    'avg_pace',
    'best_pace',
    'avg_run_cadence',
    'max_run_cadence',
    'avg_ground_contact_time_ms',
    'avg_stride_length_m',
    'avg_vertical_oscillation_cm',
    'avg_vertical_ratio',
    'avg_gct_balance',
    'avg_gap',
    'total_ascent_m',
    'total_descent_m',
    'aerobic_te',
    'training_stress_score',
    'steps',
    'avg_resp',
    'min_resp',
    'max_resp',
    'avg_stress',
    'max_stress',
    'normalized_power',
    'avg_power',
    'max_power',
    'moving_time_min',
    'elapsed_time_min',
]
