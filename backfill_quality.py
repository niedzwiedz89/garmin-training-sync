#!/usr/bin/env python3
"""
Uzupelnia nowe kolumny (te_label, ana_te, training_load, quality_json) w istniejacych
wierszach arkusza, bez kasowania danych. Uzycie: backfill_quality.py [dni] [--dry-run]
"""

import sys
import logging
from datetime import datetime, timedelta

import gspread

import config
from sync_garmin import GarminSync

logger = logging.getLogger(__name__)

NOWE_KOLUMNY = ['te_label', 'ana_te', 'training_load', 'quality_json']


def main():
    dni = 90
    dry_run = '--dry-run' in sys.argv
    for arg in sys.argv[1:]:
        if arg.isdigit():
            dni = int(arg)

    syncer = GarminSync()
    if not syncer.connect_garmin() or not syncer.connect_google_sheets():
        sys.exit(1)

    naglowki = syncer.sheet.row_values(1)
    kolumny = {name: naglowki.index(name) + 1 for name in NOWE_KOLUMNY if name in naglowki}
    if len(kolumny) != len(NOWE_KOLUMNY):
        logger.error(f"Brak kolumn w arkuszu: {set(NOWE_KOLUMNY) - set(kolumny)}")
        sys.exit(1)

    wiersz_po_id = {}
    for nr, activity_id in enumerate(syncer.sheet.col_values(1)[1:], start=2):
        if activity_id:
            wiersz_po_id[activity_id] = nr

    # bezposrednio do API - get_activities() pomija aktywnosci juz obecne w arkuszu
    koniec = datetime.now(config.TIMEZONE)
    aktywnosci = syncer.garmin_client.get_activities_by_date(
        (koniec - timedelta(days=dni)).strftime('%Y-%m-%d'), koniec.strftime('%Y-%m-%d'))
    logger.info(f"Do uzupelnienia: {len(aktywnosci)} aktywnosci z ostatnich {dni} dni")

    zmiany = []
    for activity in aktywnosci:
        nr = wiersz_po_id.get(str(activity.get('activityId', '')))
        if not nr:
            continue
        load = activity.get('activityTrainingLoad')
        wartosci = {
            'te_label': activity.get('trainingEffectLabel') or '',
            'ana_te': activity.get('anaerobicTrainingEffect') or '',
            'training_load': round(load, 1) if load else '',
            'quality_json': syncer.build_quality(activity) or '',
        }
        for nazwa, wartosc in wartosci.items():
            zmiany.append({
                'range': gspread.utils.rowcol_to_a1(nr, kolumny[nazwa]),
                'values': [[wartosc]],
            })
        logger.info(f"{activity.get('startTimeLocal', '')[:10]} w.{nr}: {wartosci['te_label']}")

    if not zmiany:
        logger.info("Nic do zapisania")
        return
    if dry_run:
        logger.info(f"[dry-run] {len(zmiany)} komorek do aktualizacji")
        return

    syncer.sheet.batch_update(zmiany, value_input_option='RAW')
    logger.info(f"Zaktualizowano {len(zmiany)} komorek w {len(zmiany) // len(NOWE_KOLUMNY)} wierszach")


if __name__ == '__main__':
    main()
