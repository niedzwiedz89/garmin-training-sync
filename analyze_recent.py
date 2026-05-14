#!/usr/bin/env python3
"""
Analyze recent training data (last 3-6 months)
"""

import pandas as pd
from datetime import datetime, timedelta

# Read the CSV
df = pd.read_csv('training_data_20251027_223321.csv')

# Convert date column
df['date'] = pd.to_datetime(df['date'])

# Filter last 6 months
six_months_ago = datetime.now() - timedelta(days=180)
three_months_ago = datetime.now() - timedelta(days=90)

df_6m = df[df['date'] >= six_months_ago].copy()
df_3m = df[df['date'] >= three_months_ago].copy()

# Filter only running
running_6m = df_6m[df_6m['activity_type'] == 'running'].copy()
running_3m = df_3m[df_3m['activity_type'] == 'running'].copy()

print("=" * 80)
print("ANALIZA OSTATNICH 6 MIESIĘCY (po kontuzji Achillesa)")
print("=" * 80)

print(f"\nOSTATNIE 6 MIESIĘCY (od {six_months_ago.strftime('%Y-%m-%d')}):")
print(f"  Łącznie treningów biegowych: {len(running_6m)}")
if len(running_6m) > 0:
    print(f"  Łączny dystans: {running_6m['distance_km'].sum():.2f} km")
    print(f"  Średni dystans: {running_6m['distance_km'].mean():.2f} km")
    print(f"  Łączny czas: {running_6m['duration_min'].sum():.1f} min ({running_6m['duration_min'].sum()/60:.1f} h)")
    print(f"  Średnie tempo: {running_6m['avg_pace'].mean():.2f} min/km")
    print(f"  Średnie tętno: {running_6m['avg_hr'].mean():.0f} bpm")
    print(f"  Tygodniowo: {len(running_6m) / 26:.1f} biegów ({running_6m['distance_km'].sum() / 26:.1f} km)")

print(f"\nOSTATNIE 3 MIESIĄCE (od {three_months_ago.strftime('%Y-%m-%d')}):")
print(f"  Łącznie treningów biegowych: {len(running_3m)}")
if len(running_3m) > 0:
    print(f"  Łączny dystans: {running_3m['distance_km'].sum():.2f} km")
    print(f"  Średni dystans: {running_3m['distance_km'].mean():.2f} km")
    print(f"  Łączny czas: {running_3m['duration_min'].sum():.1f} min ({running_3m['duration_min'].sum()/60:.1f} h)")
    print(f"  Średnie tempo: {running_3m['avg_pace'].mean():.2f} min/km")
    print(f"  Średnie tętno: {running_3m['avg_hr'].mean():.0f} bpm")
    print(f"  Tygodniowo: {len(running_3m) / 13:.1f} biegów ({running_3m['distance_km'].sum() / 13:.1f} km)")

print("\n" + "=" * 80)
print("NAJSZYBSZE BIEGI W OSTATNICH 6 MIESIĄCACH")
print("=" * 80)

# Best runs by pace
best_runs = running_6m[running_6m['distance_km'] > 5].nsmallest(10, 'avg_pace')
print("\nTOP 10 najszybszych biegów (>5 km):")
for idx, row in best_runs.iterrows():
    date_str = row['date'].strftime('%Y-%m-%d')
    dist = row['distance_km']
    time = row['duration_min']
    pace = row['avg_pace']
    hr = row['avg_hr']
    title = row['title']
    print(f"  {date_str} | {dist:.2f} km | {time:.1f} min | {pace:.2f} min/km | HR {hr:.0f} | {title}")

print("\n" + "=" * 80)
print("MIESIĘCZNA PROGRESJA")
print("=" * 80)

# Group by month
running_6m['month'] = running_6m['date'].dt.to_period('M')
monthly = running_6m.groupby('month').agg({
    'activity_id': 'count',
    'distance_km': 'sum',
    'duration_min': 'sum',
    'avg_pace': 'mean',
    'avg_hr': 'mean'
}).rename(columns={'activity_id': 'count'})

print("\nProgresja miesięczna:")
for month, row in monthly.iterrows():
    print(f"  {month}: {row['count']:.0f} biegów, {row['distance_km']:.1f} km, tempo {row['avg_pace']:.2f} min/km")

print("\n" + "=" * 80)
print("TYPY TRENINGÓW")
print("=" * 80)

# Categorize workouts
def categorize_workout(row):
    if pd.isna(row['avg_pace']) or pd.isna(row['distance_km']):
        return 'Unknown'

    pace = row['avg_pace']
    distance = row['distance_km']
    title = str(row['title']).lower()

    # Intervals / Speed work
    if 'x' in title or 'interwał' in title or 'podbiegi' in title or pace < 4.3:
        return 'Intervals/Speed'

    # Tempo runs
    elif 4.3 <= pace < 4.8:
        return 'Tempo Run'

    # Long runs
    elif distance > 12:
        return 'Long Run'

    # Easy runs
    elif pace >= 4.8:
        return 'Easy Run'

    return 'Other'

running_6m['workout_type'] = running_6m.apply(categorize_workout, axis=1)
workout_counts = running_6m['workout_type'].value_counts()

print("\nRozkład typów treningów:")
for workout_type, count in workout_counts.items():
    pct = (count / len(running_6m)) * 100
    print(f"  {workout_type}: {count} ({pct:.1f}%)")

print("\n" + "=" * 80)
print("OSTATNIE 2 TYGODNIE (obecna forma)")
print("=" * 80)

two_weeks_ago = datetime.now() - timedelta(days=14)
running_2w = running_6m[running_6m['date'] >= two_weeks_ago].copy()

print(f"\nOSTATNIE 14 DNI:")
print(f"  Biegi: {len(running_2w)}")
if len(running_2w) > 0:
    print(f"  Łączny dystans: {running_2w['distance_km'].sum():.2f} km")
    print(f"  Średnie tempo: {running_2w['avg_pace'].mean():.2f} min/km")

    print(f"\n  Szczegóły:")
    for idx, row in running_2w.sort_values('date', ascending=False).iterrows():
        date_str = row['date'].strftime('%Y-%m-%d')
        dist = row['distance_km'] if pd.notna(row['distance_km']) else 0
        time = row['duration_min'] if pd.notna(row['duration_min']) else 0
        pace = row['avg_pace'] if pd.notna(row['avg_pace']) else 0
        title = row['title']
        print(f"    {date_str} | {dist:.1f} km | {time:.0f} min | {pace:.2f} min/km | {title}")

print("\n" + "=" * 80)
