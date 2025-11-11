#!/usr/bin/env python3
"""
Upload Training Plan Workouts to Garmin Connect
Parsuje plik markdown z planem treningowym i tworzy workouts na zegarku Garmin
"""

import os
import re
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from garminconnect import Garmin
from garth.exc import GarthHTTPError
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import config
from config import GARMIN_EMAIL, GARMIN_PASSWORD, TIMEZONE


class GarminWorkoutUploader:
    """Klasa do parsowania planu treningowego i uploadu do Garmin Connect"""

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.client = None

    def connect(self):
        """Połączenie z Garmin Connect"""
        try:
            self.client = Garmin(self.email, self.password)
            self.client.login()
            print("[OK] Połączono z Garmin Connect")
            return True
        except Exception as e:
            print(f"[ERROR] Błąd logowania do Garmin Connect: {e}")
            return False

    def parse_training_plan(self, plan_file):
        """
        Parsuje plik markdown z planem treningowym
        Zwraca listę treningów w formacie:
        [{'week': 1, 'day': 'WT', 'workout_type': 'intervals', 'description': '...', 'details': {...}}, ...]
        """
        with open(plan_file, 'r', encoding='utf-8') as f:
            content = f.read()

        workouts = []
        current_week = None

        # Regex patterns
        week_pattern = r'### Tydzień (\d+)'
        day_pattern = r'^-?\s*\*\*([A-ZŁŚĆĄĘŻŹŃÓ]+):\*\* (.+)'  # Obsługuje "- **PON:**" oraz "**PON:**"

        lines = content.split('\n')

        for line in lines:
            # Wykryj tydzień
            week_match = re.match(week_pattern, line)
            if week_match:
                current_week = int(week_match.group(1))
                continue

            # Wykryj dzień treningu
            day_match = re.match(day_pattern, line)
            if day_match and current_week:
                day = day_match.group(1)
                description = day_match.group(2).strip()

                # Pomiń dni odpoczynku i dni ze siłowym
                if 'Odpoczynek' in description or 'ODPOCZYNEK' in description:
                    continue
                if 'Zwift' in description:
                    continue  # Zwift treningi pomijamy - nie są biegowe
                if 'Siła' in description and 'km' not in description:
                    continue  # Tylko siłowy bez biegu

                # Parsuj szczegóły treningu
                workout_details = self.parse_workout_details(description)

                if workout_details:
                    workouts.append({
                        'week': current_week,
                        'day': day,
                        'description': description,
                        'details': workout_details
                    })

        print(f"[OK] Sparsowano {len(workouts)} treningów biegowych z {current_week} tygodni")
        return workouts

    def parse_workout_details(self, description):
        """
        Parsuje opis treningu i wyciąga szczegóły:
        - typ treningu (podbiegi, interwały, tempo run, długi bieg)
        - interwały (ile, jaki dystans/czas, tempo, przerwa)
        - rozgrzewka/wybieganie
        """
        details = {
            'type': None,
            'warmup_km': 2,  # default
            'cooldown_km': 2,  # default
            'intervals': [],
            'total_km': 0
        }

        # Wyciągnij całkowity dystans
        total_km_match = re.search(r'= \*\*(\d+(?:\.\d+)?)\s*km\*\*', description)
        if total_km_match:
            details['total_km'] = float(total_km_match.group(1))

        # Rozgrzewka
        warmup_match = re.search(r'(\d+)\s*km\s+R', description)
        if warmup_match:
            details['warmup_km'] = int(warmup_match.group(1))

        # Wybieganie
        cooldown_match = re.search(r'(\d+)\s*km\s+WB', description)
        if cooldown_match:
            details['cooldown_km'] = int(cooldown_match.group(1))

        # PODBIEGI: 8x30s, 10x40s, etc.
        if 'Podbiegi' in description or 'podbiegi' in description:
            details['type'] = 'hill_repeats'
            hill_match = re.search(r'(\d+)x(\d+)s', description)
            if hill_match:
                reps = int(hill_match.group(1))
                duration = int(hill_match.group(2))

                # Wyciągnij recovery time (np. "90s zejście")
                recovery_match = re.search(r'(\d+)s\s+zej[sśS]cie', description)
                recovery_duration = int(recovery_match.group(1)) if recovery_match else 90

                details['intervals'] = [{
                    'repeat': reps,
                    'work_duration': duration,
                    'work_pace': '3:35',  # tempo 5K
                    'recovery_type': 'down_jog',
                    'recovery_duration': recovery_duration
                }]

        # DŁUGIE INTERWAŁY: 4x2 km, 6x1.5 km, 8x1 km, 7x1 km @ race pace
        # WAŻNE: Sprawdzamy NAJPIERW km, zanim sprawdzimy "tempo" w opisie
        elif re.search(r'\d+x[\d.]+\s*km', description):
            details['type'] = 'long_intervals'

            long_int_match = re.search(r'(\d+)x([\d.]+)\s*km\s*@\s*([\d:]+(?:-[\d:]+)?)', description)
            if long_int_match:
                reps = int(long_int_match.group(1))
                distance_km = float(long_int_match.group(2))
                pace = long_int_match.group(3).split('-')[0]

                recovery_match = re.search(r'(\d+)m?\s*(?:trucht|recovery)', description)
                recovery = int(recovery_match.group(1)) if recovery_match else 400

                details['intervals'] = [{
                    'repeat': reps,
                    'work_distance': int(distance_km * 1000),
                    'work_pace': pace,
                    'recovery_type': 'jog',
                    'recovery_distance': recovery
                }]

            # LADDER: 4-3-2 km, 2-3-4 km
            elif 'Ladder' in description or 'ladder' in description:
                ladder_match = re.search(r'(\d+)-(\d+)-(\d+)\s*km\s*@\s*([\d:]+)', description)
                if ladder_match:
                    d1, d2, d3 = int(ladder_match.group(1)), int(ladder_match.group(2)), int(ladder_match.group(3))
                    pace = ladder_match.group(4)

                    details['intervals'] = [
                        {'repeat': 1, 'work_distance': d1*1000, 'work_pace': pace, 'recovery_type': 'jog', 'recovery_distance': 400},
                        {'repeat': 1, 'work_distance': d2*1000, 'work_pace': pace, 'recovery_type': 'jog', 'recovery_distance': 400},
                        {'repeat': 1, 'work_distance': d3*1000, 'work_pace': pace, 'recovery_type': 'jog', 'recovery_distance': 400},
                    ]

        # INTERWAŁY: 8x400m, 6x600m, 5x800m, 4x1km, etc.
        elif 'Interwały' in description or 'interwały' in description:
            details['type'] = 'intervals'

            # Pattern: 8x400m @ 3:35-3:40/km
            interval_match = re.search(r'(\d+)x(\d+)m?\s*@?\s*([\d:]+(?:-[\d:]+)?)', description)
            if interval_match:
                reps = int(interval_match.group(1))
                distance = int(interval_match.group(2))
                pace = interval_match.group(3).split('-')[0]  # bierzemy szybsze tempo

                # Recovery
                recovery_match = re.search(r'(\d+)m?\s*trucht', description)
                recovery = int(recovery_match.group(1)) if recovery_match else 400

                details['intervals'] = [{
                    'repeat': reps,
                    'work_distance': distance,
                    'work_pace': pace,
                    'recovery_type': 'jog',
                    'recovery_distance': recovery
                }]

        # TEMPO RUN: 2x10 min, 3x8 min, 4x6 min @ tempo
        elif 'Tempo Run' in description or 'tempo' in description.lower():
            details['type'] = 'tempo'

            tempo_match = re.search(r'(\d+)x(\d+)\s*min\s*@\s*([\d:]+(?:-[\d:]+)?)', description)
            if tempo_match:
                reps = int(tempo_match.group(1))
                minutes = int(tempo_match.group(2))
                pace = tempo_match.group(3).split('-')[0]

                recovery_match = re.search(r'(\d+)\s*min\s+recovery', description)
                recovery_min = int(recovery_match.group(1)) if recovery_match else 2

                details['intervals'] = [{
                    'repeat': reps,
                    'work_duration': minutes * 60,
                    'work_pace': pace,
                    'recovery_type': 'jog',
                    'recovery_duration': recovery_min * 60
                }]

        # DŁUGI BIEG: BC2 z wariacjami
        elif 'Długi bieg' in description or 'BC2' in description:
            details['type'] = 'long_run'

            # Progresywny
            if 'progresywny' in description.lower():
                details['variation'] = 'progressive'
            # Z tempo finish
            elif 'ostatnie' in description and 'km' in description:
                tempo_km_match = re.search(r'ostatnie\s+(\d+)\s+km\s+@\s+([\d:]+)', description)
                if tempo_km_match:
                    details['variation'] = 'tempo_finish'
                    details['tempo_km'] = int(tempo_km_match.group(1))
                    details['tempo_pace'] = tempo_km_match.group(2)
            # Z środkową częścią tempo
            elif 'środkowe' in description.lower():
                tempo_km_match = re.search(r'środkowe\s+(\d+)\s+km\s+@\s+([\d:]+)', description)
                if tempo_km_match:
                    details['variation'] = 'tempo_middle'
                    details['tempo_km'] = int(tempo_km_match.group(1))
                    details['tempo_pace'] = tempo_km_match.group(2)
            else:
                details['variation'] = 'easy'

        return details if details['type'] else None

    def pace_to_mps(self, pace_str):
        """
        Konwertuje tempo min/km (np. '3:48') na metry/sekundę
        Garmin używa m/s jako internal unit
        """
        parts = pace_str.split(':')
        minutes = int(parts[0])
        seconds = int(parts[1])

        total_seconds_per_km = minutes * 60 + seconds
        # m/s = 1000m / seconds_per_km
        mps = 1000.0 / total_seconds_per_km
        return round(mps, 2)

    def create_distance_condition(self, distance_meters):
        """
        Tworzy prawidłową strukturę endCondition dla dystansu
        zgodną z formatem Garmin Connect
        """
        return {
            "endCondition": {
                "conditionTypeId": 3,
                "conditionTypeKey": "distance"
            },
            "endConditionValue": float(distance_meters),
            "preferredEndConditionUnit": {
                "unitId": 2,
                "unitKey": "kilometer",
                "factor": 100000.0
            }
        }

    def create_time_condition(self, duration_seconds):
        """
        Tworzy prawidłową strukturę endCondition dla czasu
        zgodną z formatem Garmin Connect
        Garmin używa sekund bezpośrednio, bez preferredEndConditionUnit
        """
        return {
            "endCondition": {
                "conditionTypeId": 2,
                "conditionTypeKey": "time"
            },
            "endConditionValue": float(duration_seconds),
            "preferredEndConditionUnit": None
        }

    def generate_garmin_workout_json(self, workout):
        """
        Generuje workout JSON w formacie Garmin Connect
        """
        workout_id = random.randint(1000000, 9999999)

        # Base template
        workout_json = {
            "workoutId": workout_id,
            "ownerId": None,  # zostanie wypełnione przy upload
            "workoutName": f"Tydzień {workout['week']}: {workout['day']}",
            "description": workout['description'][:250],  # max 250 chars
            "sportType": {
                "sportTypeId": 1,
                "sportTypeKey": "running"
            },
            "workoutSegments": []
        }

        details = workout['details']
        steps = []
        step_id = random.randint(7000000000, 7999999999)

        # WARMUP
        if details['warmup_km'] > 0:
            warmup_step = {
                "type": "ExecutableStepDTO",
                "stepId": step_id,
                "stepOrder": len(steps) + 1,
                "stepType": {
                    "stepTypeId": 1,
                    "stepTypeKey": "warmup"
                },
                "targetType": {
                    "workoutTargetTypeId": 1,
                    "workoutTargetTypeKey": "no.target"
                },
                "targetValueOne": None,
                "targetValueTwo": None
            }
            warmup_step.update(self.create_distance_condition(details['warmup_km'] * 1000))
            steps.append(warmup_step)
            step_id += 1

        # MAIN WORKOUT
        if details['type'] in ['intervals', 'long_intervals', 'hill_repeats', 'tempo']:
            for interval_set in details['intervals']:
                repeat_steps = []

                # Work interval
                work_step = {
                    "type": "ExecutableStepDTO",
                    "stepId": step_id,
                    "stepOrder": 1,
                    "stepType": {
                        "stepTypeId": 3,
                        "stepTypeKey": "interval"
                    }
                }
                step_id += 1

                # End condition: distance or time
                if 'work_distance' in interval_set:
                    work_step.update(self.create_distance_condition(interval_set['work_distance']))
                else:  # duration
                    work_step.update(self.create_time_condition(interval_set['work_duration']))

                # Target: pace
                if 'work_pace' in interval_set:
                    pace_mps = self.pace_to_mps(interval_set['work_pace'])
                    work_step["targetType"] = {
                        "workoutTargetTypeId": 6,
                        "workoutTargetTypeKey": "pace.zone"
                    }
                    work_step["targetValueOne"] = pace_mps - 0.15  # -10 sec/km tolerance
                    work_step["targetValueTwo"] = pace_mps + 0.15  # +10 sec/km tolerance
                else:
                    work_step["targetType"] = {
                        "workoutTargetTypeId": 1,
                        "workoutTargetTypeKey": "no.target"
                    }
                    work_step["targetValueOne"] = None
                    work_step["targetValueTwo"] = None

                repeat_steps.append(work_step)

                # Recovery
                recovery_step = {
                    "type": "ExecutableStepDTO",
                    "stepId": step_id,
                    "stepOrder": 2,
                    "stepType": {
                        "stepTypeId": 4,
                        "stepTypeKey": "recovery"
                    }
                }
                step_id += 1

                if 'recovery_distance' in interval_set:
                    recovery_step.update(self.create_distance_condition(interval_set['recovery_distance']))
                else:
                    recovery_step.update(self.create_time_condition(interval_set['recovery_duration']))

                recovery_step["targetType"] = {
                    "workoutTargetTypeId": 1,
                    "workoutTargetTypeKey": "no.target"
                }
                recovery_step["targetValueOne"] = None
                recovery_step["targetValueTwo"] = None

                repeat_steps.append(recovery_step)

                # Wrap in repeat step
                repeat_step = {
                    "type": "RepeatGroupDTO",
                    "stepId": step_id,
                    "stepOrder": len(steps) + 1,
                    "numberOfIterations": interval_set['repeat'],
                    "workoutSteps": repeat_steps
                }
                step_id += 1

                steps.append(repeat_step)

        elif details['type'] == 'long_run':
            # Długi bieg - pojedynczy step z targetem czasu/dystansu
            main_distance = details['total_km'] - details['warmup_km'] - details['cooldown_km']

            if details.get('variation') == 'tempo_finish':
                # Easy part
                easy_distance = main_distance - details['tempo_km']
                easy_step = {
                    "type": "ExecutableStepDTO",
                    "stepId": step_id,
                    "stepOrder": len(steps) + 1,
                    "stepType": {
                        "stepTypeId": 3,
                        "stepTypeKey": "interval"
                    },
                    "targetType": {
                        "workoutTargetTypeId": 1,
                        "workoutTargetTypeKey": "no.target"
                    },
                    "targetValueOne": None,
                    "targetValueTwo": None
                }
                easy_step.update(self.create_distance_condition(int(easy_distance * 1000)))
                steps.append(easy_step)
                step_id += 1

                # Tempo finish
                pace_mps = self.pace_to_mps(details['tempo_pace'])
                tempo_step = {
                    "type": "ExecutableStepDTO",
                    "stepId": step_id,
                    "stepOrder": len(steps) + 1,
                    "stepType": {
                        "stepTypeId": 3,
                        "stepTypeKey": "interval"
                    },
                    "targetType": {
                        "workoutTargetTypeId": 6,
                        "workoutTargetTypeKey": "pace.zone"
                    },
                    "targetValueOne": pace_mps - 0.15,
                    "targetValueTwo": pace_mps + 0.15
                }
                tempo_step.update(self.create_distance_condition(details['tempo_km'] * 1000))
                steps.append(tempo_step)
                step_id += 1

            else:
                # Easy run - no target
                easy_run_step = {
                    "type": "ExecutableStepDTO",
                    "stepId": step_id,
                    "stepOrder": len(steps) + 1,
                    "stepType": {
                        "stepTypeId": 3,
                        "stepTypeKey": "interval"
                    },
                    "targetType": {
                        "workoutTargetTypeId": 1,
                        "workoutTargetTypeKey": "no.target"
                    },
                    "targetValueOne": None,
                    "targetValueTwo": None
                }
                easy_run_step.update(self.create_distance_condition(int(main_distance * 1000)))
                steps.append(easy_run_step)
                step_id += 1

        # COOLDOWN
        if details['cooldown_km'] > 0:
            cooldown_step = {
                "type": "ExecutableStepDTO",
                "stepId": step_id,
                "stepOrder": len(steps) + 1,
                "stepType": {
                    "stepTypeId": 2,
                    "stepTypeKey": "cooldown"
                },
                "targetType": {
                    "workoutTargetTypeId": 1,
                    "workoutTargetTypeKey": "no.target"
                },
                "targetValueOne": None,
                "targetValueTwo": None
            }
            cooldown_step.update(self.create_distance_condition(details['cooldown_km'] * 1000))
            steps.append(cooldown_step)

        # Add segment with all steps
        workout_json["workoutSegments"] = [{
            "segmentOrder": 1,
            "sportType": {
                "sportTypeId": 1,
                "sportTypeKey": "running"
            },
            "workoutSteps": steps
        }]

        return workout_json

    def upload_workout(self, workout_json):
        """
        Uploaduje workout JSON do Garmin Connect przez API
        """
        if not self.client:
            print("[ERROR] Brak połączenia z Garmin Connect")
            return False

        try:
            # Upload using garminconnect API
            result = self.client.upload_workout(workout_json)
            workout_id = result.get('workoutId')
            print(f"[OK] Workout '{workout_json['workoutName']}' uploaded (ID: {workout_id})")
            return workout_id

        except Exception as e:
            print(f"[ERROR] Błąd podczas uploadu: {e}")
            return False

    def schedule_workout(self, workout_id, date):
        """
        Scheduleuje workout na konkretną datę w kalendarzu Garmin
        Używa /proxy/workout-service/schedule/{workout_id}
        """
        try:
            # Endpoint: POST /proxy/workout-service/schedule/{workout_id}
            schedule_url = f"/proxy/workout-service/schedule/{workout_id}"
            schedule_payload = {
                "date": date.strftime("%Y-%m-%d")
            }

            # Użyj garth.post
            result = self.client.garth.post("connect", schedule_url, json=schedule_payload)

            if result.status_code in [200, 201, 204]:
                print(f"    -> Scheduled for {date.strftime('%Y-%m-%d')}")
                return True
            else:
                print(f"  [ERROR] Nie udało się zaplanować: {result.status_code}")
                print(f"  [ERROR] Response: {result.text}")
                return False

        except Exception as e:
            print(f"  [ERROR] Błąd planowania: {e}")
            return False


def main():
    """Main function"""
    print("=" * 60)
    print("Garmin Workout Uploader - Upload Training Plan")
    print("=" * 60)

    # Path do planu treningowego
    plan_file = Path(__file__).parent / 'plan' / 'plan_treningowy_10km_38min.md'

    if not plan_file.exists():
        print(f"[ERROR] Nie znaleziono pliku: {plan_file}")
        return

    print(f"\nPlan treningowy: {plan_file.name}")

    # Inicjalizacja uploadera
    uploader = GarminWorkoutUploader(GARMIN_EMAIL, GARMIN_PASSWORD)

    # Połącz z Garmin Connect
    if not uploader.connect():
        return

    # Parsuj plan treningowy
    print("\nParsowanie planu treningowego...")
    workouts = uploader.parse_training_plan(plan_file)

    if not workouts:
        print("[ERROR] Nie znaleziono treningów do uploadu")
        return

    # Pytaj użytkownika
    print(f"\nZnaleziono {len(workouts)} treningów biegowych.")
    print("\nOpcje:")
    print("1. Upload wszystkich treningów (bez schedulowania)")
    print("2. Upload + scheduluj od dzisiejszej daty")
    print("3. Upload + scheduluj od konkretnej daty")
    print("4. Tylko generuj JSON (bez uploadu)")
    print("5. Anuluj")

    choice = input("\nWybierz opcję (1-5): ").strip()

    if choice == '5':
        print("Anulowano.")
        return

    start_date = None
    if choice == '2':
        start_date = datetime.now(TIMEZONE)
        # Zaokrąglij do poniedziałku obecnego tygodnia
        days_since_monday = start_date.weekday()
        start_date = start_date - timedelta(days=days_since_monday)
        print(f"Start date: {start_date.strftime('%Y-%m-%d')} (najbliższy poniedziałek)")

    elif choice == '3':
        date_str = input("Podaj datę startu (YYYY-MM-DD): ").strip()
        try:
            start_date = datetime.strptime(date_str, "%Y-%m-%d")
            start_date = TIMEZONE.localize(start_date)
        except ValueError:
            print("[ERROR] Nieprawidłowy format daty")
            return

    # Mapowanie dni na offset
    day_offset = {
        'PON': 0, 'WT': 1, 'ŚR': 2, 'CZW': 3, 'PT': 4, 'SOB': 5, 'NIEDZ': 6
    }

    # Proces uploadu
    print("\n" + "=" * 60)
    if choice == '4':
        print("Generowanie JSON...")
        output_dir = Path(__file__).parent / 'plan' / 'workouts_json'
        output_dir.mkdir(exist_ok=True)

        for workout in workouts:
            workout_json = uploader.generate_garmin_workout_json(workout)
            filename = f"week{workout['week']:02d}_{workout['day']}.json"

            with open(output_dir / filename, 'w', encoding='utf-8') as f:
                json.dump(workout_json, f, indent=2, ensure_ascii=False)

            print(f"[OK] {filename}")

        print(f"\n[OK] Wygenerowano {len(workouts)} plików JSON w: {output_dir}")

    else:
        print("Uploading workouts...")
        success_count = 0

        for workout in workouts:
            # Generate JSON
            workout_json = uploader.generate_garmin_workout_json(workout)

            # Upload
            workout_id = uploader.upload_workout(workout_json)
            if workout_id:
                success_count += 1

                # Schedule if requested
                if start_date and choice in ['2', '3']:
                    # Oblicz datę dla tego treningu
                    week_offset = (workout['week'] - 1) * 7
                    day_off = day_offset.get(workout['day'], 0)
                    workout_date = start_date + timedelta(days=week_offset + day_off)

                    uploader.schedule_workout(workout_id, workout_date)

        print("\n" + "=" * 60)
        print(f"[OK] Zakończono: {success_count}/{len(workouts)} treningów uploaded")
        print("=" * 60)


if __name__ == '__main__':
    main()
