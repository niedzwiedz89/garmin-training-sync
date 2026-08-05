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
import sys
from garminconnect import Garmin
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
        # Ten sam tokenstore co sync_garmin.py - logowanie hasłem wywołuje 429/MFA po stronie Garmina
        tokenstore = os.getenv('GARMINTOKENS') or os.path.join(
            os.path.expanduser("~"), ".garth_sync_garmin")
        try:
            self.client = Garmin(self.email, self.password)
            try:
                self.client.login(tokenstore)
            except Exception:
                self.client.login()
                if len(tokenstore) <= 512:
                    self.client.client.dump(tokenstore)
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
        - typ treningu (podbiegi, interwały, tempo run, długi bieg, easy run, steady state)
        - interwały (ile, jaki dystans/czas, tempo, przerwa)
        - rozgrzewka/wybieganie (km lub minuty)

        Obsługuje formaty:
        - Stary: "X km R/WB", "Interwały", "BC2", "Długi bieg"
        - Nowy (plan BS): "BS X min", "RPE X/Y", "Nx(Xs / Ys)", "@tempo 5k"
        """
        details = {
            'type': None,
            'warmup_km': 2,           # default dystans rozgrzewki
            'warmup_seconds': None,   # czas rozgrzewki (nowy format BS)
            'cooldown_km': 2,         # default dystans wybiegania
            'cooldown_seconds': None, # czas wybiegania (nowy format BS)
            'main_seconds': None,     # czas głównej części (easy/long run)
            'intervals': [],
            'total_km': 0
        }

        # Wyciągnij całkowity dystans (obsługuje też ~19 km)
        total_km_match = re.search(r'=\s*\*\*~?(\d+(?:\.\d+)?)\s*km\*\*', description)
        if total_km_match:
            details['total_km'] = float(total_km_match.group(1))

        # --- Rozgrzewka i wybieganie (stary styl km) ---
        warmup_km_match = re.search(r'(\d+)\s*km\s+R\b', description)
        if warmup_km_match:
            details['warmup_km'] = int(warmup_km_match.group(1))

        cooldown_km_match = re.search(r'(\d+)\s*km\s+WB\b', description)
        if cooldown_km_match:
            details['cooldown_km'] = int(cooldown_km_match.group(1))

        # Nowy styl (plan BS): "BS X min + [główny trening] + BS Y min ="
        has_complex_workout = bool(
            re.search(r'\d+x', description) or
            re.search(r'Bieg Ciągły', description, re.IGNORECASE) or
            re.search(r'\bRPE\b', description) or
            'BNP' in description
        )
        if has_complex_workout:
            warmup_bs = re.match(r'(?:Długi\s+)?BS\s+(\d+)\s+min\s*\+', description)
            if warmup_bs:
                details['warmup_seconds'] = int(warmup_bs.group(1)) * 60
                details['warmup_km'] = 0  # używamy czasu zamiast dystansu
            cooldown_bs = re.search(r'\+\s*BS\s+(\d+)\s+min\s*=', description)
            if cooldown_bs:
                details['cooldown_seconds'] = int(cooldown_bs.group(1)) * 60
                details['cooldown_km'] = 0  # używamy czasu zamiast dystansu

        # --- Pomocnicze funkcje ---
        def parse_duration(time_str, is_seconds=False):
            """Parsuje czas: '1:30' → 90s, '40' → 40s (is_seconds=True), '2' → 120s (minuty)"""
            if ':' in time_str:
                parts = time_str.split(':')
                return int(parts[0]) * 60 + int(parts[1])
            val = int(time_str)
            return val if is_seconds else val * 60

        def rpe_to_pace(rpe_str):
            """Konwertuje RPE do tempa: RPE 7 ≈ HM pace (4:02), RPE 8 ≈ 10k pace (3:52)"""
            try:
                rpe_val = float(re.split(r'[/\-]', rpe_str.strip())[0])
            except (ValueError, IndexError):
                rpe_val = 7.0
            if rpe_val >= 8:
                return '3:52'
            elif rpe_val >= 7:
                return '4:02'
            else:
                return '4:30'

        # ==================== DETEKCJA TYPU ====================

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
                try:
                    pace = long_int_match.group(3).split('-')[1]
                except Exception as e:
                   print(f'Pojawia się błąd {e}')
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

        # INTERWAŁY: 8x400m, 6x600m, 5x800m, 4x1km, etc. (stary styl ze słowem "Interwały")
        elif 'Interwały' in description or 'interwały' in description:
            details['type'] = 'intervals'

            # Pattern: 8x400m @ 3:35-3:40/km
            interval_match = re.search(r'(\d+)x(\d+)m?\s*@?\s*([\d:]+(?:-[\d:]+)?)', description)
            if interval_match:
                reps = int(interval_match.group(1))
                distance = int(interval_match.group(2))

                try:
                    pace = interval_match.group(3).split('-')[1]
                except Exception as e:
                   print(f'Pojawia się błąd {e}')
                   pace = interval_match.group(3).split('-')[0]

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

        # NOWE: Interwały RPE minutowe: NxN min (RPE X) na N(:NN) min/trucht
        # Przykłady: 6x4 min (RPE 7) na 1 min trucht | 8x5 min (RPE 7-8) na 1:30 trucht
        elif re.search(r'\d+x\d+\s*min\s*\(RPE', description, re.IGNORECASE):
            details['type'] = 'tempo'
            rpe_match = re.search(
                r'(\d+)x(\d+)\s*min\s*\(RPE\s*([\d./\-]+)\)\s*na\s*(\d+(?::\d+)?)\s*(?:min\s*)?trucht',
                description, re.IGNORECASE
            )
            if rpe_match:
                reps = int(rpe_match.group(1))
                work_min = int(rpe_match.group(2))
                rpe_str = rpe_match.group(3)
                rest_str = rpe_match.group(4)
                details['intervals'] = [{
                    'repeat': reps,
                    'work_duration': work_min * 60,
                    'work_pace': rpe_to_pace(rpe_str),
                    'recovery_type': 'jog',
                    'recovery_duration': parse_duration(rest_str)
                }]

        # NOWE: Interwały @ tempo 5k/5-10k (czasowe)
        # Przykłady: 15x(1 min @tempo 5k / 1 min trucht)
        #            20x(40" @tempo 5k / 1:20 trucht)
        #            10x(1:30 @tempo 5k / 1:30 trucht)
        #            8x(2 min @tempo 5-10k / 2 min trucht)
        elif re.search(r'\d+x\(.*?@tempo', description, re.IGNORECASE):
            details['type'] = 'intervals'
            m = re.search(
                r'(\d+)x\(\s*(\d+(?::\d+)?)(["\']?)\s*(?:min\s*)?@tempo\s*[\d\w\s\-]+?/\s*(\d+(?::\d+)?)\s*(?:min\s*)?trucht\)',
                description, re.IGNORECASE
            )
            if m:
                reps = int(m.group(1))
                work_str = m.group(2)
                had_quote = bool(m.group(3))  # True = czas podany w sekundach (np. 40")
                rest_str = m.group(4)
                details['intervals'] = [{
                    'repeat': reps,
                    'work_duration': parse_duration(work_str, is_seconds=had_quote),
                    'work_pace': '3:40',  # ~tempo 5km dla HM 1:25
                    'recovery_type': 'jog',
                    'recovery_duration': parse_duration(rest_str)
                }]

        # NOWE: Interwały sekundowe: Nx(Xs szybko / Ys trucht) lub Nx(X"/Y")
        # Przykłady: 10x(20" szybko / 40" trucht) | 10x(30" szybko / 1 min trucht) | 5x(20"/40")
        elif re.search(r'\d+x\(\d+["\']\s*(?:szybko|dynamicznie|/)', description):
            details['type'] = 'intervals'
            # Wariant 1: oba czasy w sekundach (z cudzysłowem)
            sec_match = re.search(
                r'(\d+)x\((\d+)["\']\s*(?:szybko|dynamicznie)?\s*/\s*(\d+)["\']\s*(?:luź?ny\s*)?trucht\)',
                description
            )
            rest_has_quote = True
            if not sec_match:
                # Wariant 2: praca w sekundach, odpoczynek w minutach lub MM:SS
                sec_match = re.search(
                    r'(\d+)x\((\d+)["\']\s*(?:szybko|dynamicznie)?\s*/\s*(\d+(?::\d+)?)\s*(?:min\s*)?trucht\)',
                    description
                )
                rest_has_quote = False
            if not sec_match:
                # Wariant 3: Nx(X"/Y") bez słów opisowych - oba czasy w sekundach
                sec_match = re.search(r'(\d+)x\((\d+)["\']/(\d+)["\']\)', description)
                rest_has_quote = True
            if sec_match:
                reps = int(sec_match.group(1))
                work_sec = int(sec_match.group(2))
                rest_str = sec_match.group(3)
                # Tempa z realnych wykonań tych odcinków; szerokie widełki, bo plan zakłada
                # bieg "z zapasem" - cel ma mierzyć, a nie prowadzić w trakcie odcinka
                if work_sec <= 25:
                    short_pace = '3:25'
                elif work_sec <= 35:
                    short_pace = '3:28'
                else:
                    short_pace = '3:15'

                details['intervals'] = [{
                    'repeat': reps,
                    'work_duration': work_sec,  # już w sekundach
                    'work_pace': short_pace,
                    'pace_tolerance': 12,
                    'recovery_type': 'jog',
                    'recovery_duration': parse_duration(rest_str, is_seconds=rest_has_quote)
                }]

        # NOWE: Minutowe podbicia "dynamicznie/szybko": 8x1 min dynamicznie na 1 min trucht
        elif re.search(r'\d+x\d+\s*min\s+(?:dynamicznie|szybko)', description, re.IGNORECASE):
            details['type'] = 'intervals'
            m = re.search(
                r'(\d+)x(\d+)\s*min\s+(?:dynamicznie|szybko).*?na\s+(\d+(?::\d+)?)\s*(?:min\s*)?trucht',
                description, re.IGNORECASE
            )
            if m:
                reps = int(m.group(1))
                work_min = int(m.group(2))
                rest_str = m.group(3)
                details['intervals'] = [{
                    'repeat': reps,
                    'work_duration': work_min * 60,
                    'work_pace': '3:40',
                    'recovery_type': 'jog',
                    'recovery_duration': parse_duration(rest_str)
                }]

        # NOWE: Bieg ciągły z RPE: "30 min Bieg Ciągły (RPE 7)" lub "30 min (RPE 7)"
        elif re.search(r'\d+\s*min\s*(?:Bieg\s*Ciągły\s*)?\(RPE', description, re.IGNORECASE):
            details['type'] = 'steady_state'
            steady_match = re.search(
                r'(\d+)\s*min\s*(?:Bieg\s*Ciągły\s*)?\(RPE\s*([\d./\-]+)\)',
                description, re.IGNORECASE
            )
            if steady_match:
                details['main_seconds'] = int(steady_match.group(1)) * 60
                details['steady_pace'] = rpe_to_pace(steady_match.group(2))

        # NOWE: BNP - Bieg z Narastającą Prędkością (progresywny)
        elif 'BNP' in description:
            details['type'] = 'long_run'
            details['variation'] = 'progressive'
            bnp_match = re.match(r'(\d+)\s*min\s*BNP', description)
            if bnp_match:
                details['main_seconds'] = int(bnp_match.group(1)) * 60
            # Cały czas w opisie, bez osobnej rozgrzewki/wybiegania
            details['warmup_km'] = 0
            details['cooldown_km'] = 0
            details['warmup_seconds'] = None
            details['cooldown_seconds'] = None

        # TEMPO RUN: 2x10 min, 3x8 min, 4x6 min @ tempo (stary format)
        elif 'Tempo Run' in description or 'tempo' in description.lower():
            details['type'] = 'tempo'

            tempo_match = re.search(r'(\d+)x(\d+)\s*min\s*@\s*([\d:]+(?:-[\d:]+)?)', description)
            if tempo_match:
                reps = int(tempo_match.group(1))
                minutes = int(tempo_match.group(2))

                try:
                    pace = tempo_match.group(3).split('-')[1]
                except Exception as e:
                   print(f'Pojawia się błąd {e}')
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

        # DŁUGI BIEG: BC2 z wariacjami (stary format)
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

        # NOWE: Długi bieg spokojny BS: "Długi BS X min"
        elif re.match(r'Długi\s+BS\s+\d+\s*min', description):
            details['type'] = 'long_run'
            details['variation'] = 'easy'
            long_bs_match = re.match(r'Długi\s+BS\s+(\d+)\s*min', description)
            if long_bs_match:
                details['main_seconds'] = int(long_bs_match.group(1)) * 60
            details['warmup_km'] = 0
            details['cooldown_km'] = 0

        # NOWE: Prosty bieg spokojny BS: "BS X min"
        elif re.match(r'BS\s+\d+\s*min', description):
            details['type'] = 'easy_run'
            bs_match = re.match(r'BS\s+(\d+)\s*min', description)
            if bs_match:
                details['main_seconds'] = int(bs_match.group(1)) * 60
            details['warmup_km'] = 0
            details['cooldown_km'] = 0

        # Walidacja: typy wymagające interwałów muszą je mieć (np. nie parsujemy startu wyścigu)
        if details['type'] in ['intervals', 'long_intervals', 'hill_repeats', 'tempo'] and not details['intervals']:
            return None

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

    def pace_window(self, pace_str, tolerance_s=10):
        """
        Widełki tempa w m/s z tolerancji podanej w sek/km. Stałe +-0.15 m/s dawało przy
        odcinkach 3:15/km tylko +-6 s/km, a przy 4:00/km +-9 s/km.
        Zwraca (wolniejsze, szybsze) - Garmin oczekuje targetValueOne < targetValueTwo.
        """
        minutes, seconds = pace_str.split(':')
        base = int(minutes) * 60 + int(seconds)
        return round(1000.0 / (base + tolerance_s), 3), round(1000.0 / (base - tolerance_s), 3)

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

        short_title = re.split(r'[\(,\+]', workout['description'])[0].strip()

        # Base template
        workout_json = {
            "workoutId": workout_id,
            "ownerId": None,  # zostanie wypełnione przy upload
            "workoutName": f"Tydzień{workout['week']}:{workout['day']}: {short_title}",
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
        if details.get('warmup_seconds') or details['warmup_km'] > 0:
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
            if details.get('warmup_seconds'):
                warmup_step.update(self.create_time_condition(details['warmup_seconds']))
            else:
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
                if interval_set.get('work_pace'):
                    wolniej, szybciej = self.pace_window(
                        interval_set['work_pace'], interval_set.get('pace_tolerance', 10))
                    work_step["targetType"] = {
                        "workoutTargetTypeId": 6,
                        "workoutTargetTypeKey": "pace.zone"
                    }
                    work_step["targetValueOne"] = wolniej
                    work_step["targetValueTwo"] = szybciej
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
            if details.get('main_seconds'):
                # Czas-based: Długi BS lub BNP
                main_step = {
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
                main_step.update(self.create_time_condition(details['main_seconds']))
                steps.append(main_step)
                step_id += 1
            else:
                # Dystans-based: stary BC2/Długi bieg
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
                    wolniej, szybciej = self.pace_window(details['tempo_pace'])
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
                        "targetValueOne": wolniej,
                        "targetValueTwo": szybciej
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

        elif details['type'] == 'easy_run':
            # Prosty bieg spokojny (BS X min) - cały trening w jednym stepie czasowym
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
            if details.get('main_seconds'):
                easy_step.update(self.create_time_condition(details['main_seconds']))
            elif details['total_km'] > 0:
                easy_step.update(self.create_distance_condition(int(details['total_km'] * 1000)))
            else:
                easy_step.update(self.create_time_condition(3600))  # fallback 1h
            steps.append(easy_step)
            step_id += 1

        elif details['type'] == 'steady_state':
            # Bieg ciągły z zadanym tempem RPE
            pace_mps = self.pace_to_mps(details.get('steady_pace', '4:02'))
            steady_step = {
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
            if details.get('main_seconds'):
                steady_step.update(self.create_time_condition(details['main_seconds']))
            else:
                steady_step.update(self.create_time_condition(1800))  # fallback 30 min
            steps.append(steady_step)
            step_id += 1

        # COOLDOWN
        if details.get('cooldown_seconds') or details['cooldown_km'] > 0:
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
            if details.get('cooldown_seconds'):
                cooldown_step.update(self.create_time_condition(details['cooldown_seconds']))
            else:
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
        """Scheduleuje workout na konkretną datę w kalendarzu Garmin"""
        date_str = date.strftime("%Y-%m-%d")
        try:
            self.client.schedule_workout(workout_id, date_str)
            print(f"    -> Scheduled for {date_str}")
            return True
        except Exception as e:
            print(f"  [ERROR] Błąd planowania: {e}")
            return False


def main(plan_file_path=None):
    """Main function"""
    print("=" * 60)
    print("Garmin Workout Uploader - Upload Training Plan")
    print("=" * 60)

    # Path do planu treningowego
    if plan_file_path:
        plan_file = Path(plan_file_path)
    else:
        plan_file = Path(__file__).parent / 'plan' / 'plan_treningowy_21km_85min.md'        

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
    if sys.argv[1:]:
        main(plan_file_path=sys.argv[1])
    else:
        main()
