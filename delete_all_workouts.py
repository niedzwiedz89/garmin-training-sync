#!/usr/bin/env python3
"""
Delete all training plan workouts from Garmin Connect
Usuwa wszystkie workouty które zaczynają się od "Tydzień"
"""

from dotenv import load_dotenv
import time

load_dotenv()

from upload_workouts_to_garmin import GarminWorkoutUploader
from config import GARMIN_EMAIL, GARMIN_PASSWORD

def main():
    print("="*60)
    print("Usuwanie wszystkich workoutów z planu treningowego")
    print("="*60)

    # Inicjalizacja
    uploader = GarminWorkoutUploader(GARMIN_EMAIL, GARMIN_PASSWORD)

    # Połącz
    if not uploader.connect():
        print("Błąd połączenia z Garmin Connect")
        return

    print("\nPobieranie listy workoutów...")

    try:
        # Pobierz pierwsze 100 workoutów (powinno wystarczyć dla naszych 60)
        workouts = uploader.client.get_workouts(0, 100)

        # Filtruj tylko te które zaczynają się od "Tydzień"
        plan_workouts = [w for w in workouts if w.get('workoutName', '').startswith('Tydzień')]

        print(f"\nZnaleziono {len(plan_workouts)} workoutów do usunięcia:")
        for w in plan_workouts[:10]:  # Pokaż pierwsze 10
            print(f"  - {w['workoutName']} (ID: {w['workoutId']})")
        if len(plan_workouts) > 10:
            print(f"  ... i {len(plan_workouts) - 10} więcej")

        # Potwierdź
        confirm = input(f"\nUsunąć {len(plan_workouts)} workoutów? (tak/nie): ").strip().lower()

        if confirm not in ['tak', 't', 'yes', 'y']:
            print("Anulowano.")
            return

        # Usuń wszystkie
        print("\nUsuwanie workoutów...")
        deleted = 0
        failed = 0

        for workout in plan_workouts:
            workout_id = workout['workoutId']
            workout_name = workout['workoutName']

            try:
                # Użyj garth bezpośrednio - DELETE /workout-service/workout/{id}
                delete_url = f"/workout-service/workout/{workout_id}"
                result = uploader.client.garth.delete("connectapi", delete_url)

                if result.status_code in [200, 201, 204]:
                    print(f"[OK] Usunięto: {workout_name}")
                    deleted += 1
                else:
                    print(f"[ERROR] Nie udało się usunąć {workout_name}: HTTP {result.status_code}")
                    failed += 1

                time.sleep(0.5)  # Delay żeby nie przeciążyć API
            except Exception as e:
                print(f"[ERROR] Nie udało się usunąć {workout_name}: {e}")
                failed += 1

        print("\n" + "="*60)
        print(f"Zakończono: {deleted} usunięto, {failed} błędów")
        print("="*60)

    except Exception as e:
        print(f"[ERROR] Błąd: {e}")

if __name__ == '__main__':
    main()
