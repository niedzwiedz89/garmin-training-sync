# Garmin Training Sync

Automatyczna synchronizacja aktywności treningowych z Garmin Connect do Google Sheets + upload planów treningowych do zegarka Garmin.

## Funkcje

### Synchronizacja treningów (Garmin → Google Sheets)
- Automatyczna synchronizacja treningów z Garmin Connect
- Zapis do Google Sheets online
- Obsługa 30+ metryk treningowych (dystans, tempo, tętno, kadencja, etc.)
- Automatyzacja przez GitHub Actions (2x dziennie)
- Unikanie duplikatów
- Szczegółowe logowanie
- Retry logic przy błędach połączenia

### Upload workoutów (Plan → Garmin) 🆕
- Parser planu treningowego z formatu Markdown
- Automatyczne tworzenie strukturowanych workoutów Garmin
- Wsparcie dla różnych typów treningów:
  - Podbiegi (hill repeats)
  - Interwały (400m, 800m, 1km, 2km+)
  - Tempo run
  - Długie biegi z wariacjami
- Poprawna obsługa tempów, dystansów i czasów recovery
- Masowy upload wszystkich workoutów z 16-tygodniowego planu

## Metryki treningowe

### Podstawowe (wszystkie aktywności)
- Typ aktywności (Running, Cycling, Cardio, Yoga, etc.)
- Data i czas
- Tytuł aktywności
- Dystans (km)
- Czas trwania (minuty)
- Kalorie
- Średnie i maksymalne tętno
- Średnie i najlepsze tempo

### Zaawansowane (głównie bieganie)
- Kadencja (średnia i maksymalna)
- Czas kontaktu z podłożem (GCT)
- Długość kroku
- Oscylacja wertykalna
- Vertical ratio
- GCT balance
- Grade Adjusted Pace (GAP)
- Wzniesienia i zjazdy

### Dodatkowe
- Aerobic Training Effect
- Training Stress Score
- Kroki
- Dane oddechowe (respiracja)
- Poziom stresu
- Moc (dla kolarstwa)
- I więcej...

## Wymagania

- Konto Garmin Connect
- Konto Google (do Google Sheets)
- Konto GitHub (do automatyzacji)
- Python 3.11+ (do testowania lokalnego)

## Instalacja i konfiguracja

### 1. Utwórz Google Service Account

1. Przejdź do [Google Cloud Console](https://console.cloud.google.com/)
2. Stwórz nowy projekt lub wybierz istniejący
3. Włącz Google Sheets API i Google Drive API:
   - Menu → APIs & Services → Library
   - Wyszukaj "Google Sheets API" → Enable
   - Wyszukaj "Google Drive API" → Enable
4. Stwórz Service Account:
   - Menu → IAM & Admin → Service Accounts
   - Create Service Account
   - Nadaj nazwę (np. "garmin-sync")
   - Create and Continue
5. Pobierz klucz JSON:
   - Kliknij na utworzony service account
   - Keys → Add Key → Create new key
   - Wybierz JSON
   - Pobierz plik (będzie potrzebny w następnym kroku)
6. Skopiuj email service account (format: `nazwa@projekt.iam.gserviceaccount.com`)

### 2. Przygotuj Google Sheets

1. Stwórz nowy Google Sheets lub otwórz istniejący
2. Nazwij go **dokładnie** `garmin_trainings` (lub zmień nazwę w `config.py`)
3. Udostępnij go dla service account:
   - Kliknij "Share" (Udostępnij)
   - Wklej email service account
   - Nadaj uprawnienia "Editor"
   - Wyłącz "Notify people" (nie wysyłaj powiadomienia)
   - Share

### 3. Sklonuj repozytorium

```bash
git clone https://github.com/twoj-username/garmin-training-sync.git
cd garmin-training-sync
```

### 4. Konfiguracja GitHub Secrets

Przejdź do ustawień swojego repozytorium GitHub:

1. Settings → Secrets and variables → Actions → New repository secret

2. Dodaj 3 sekrety:

   **GARMIN_EMAIL**
   ```
   your-garmin-email@example.com
   ```

   **GARMIN_PASSWORD**
   ```
   your-garmin-password
   ```

   **GOOGLE_SHEETS_CREDENTIALS**

   Otwórz pobrany plik JSON z kluczem service account i skopiuj **całą** jego zawartość jako jedną linię:
   ```json
   {"type":"service_account","project_id":"your-project","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}
   ```

### 5. Włącz GitHub Actions

1. Przejdź do zakładki "Actions" w swoim repozytorium
2. Jeśli pojawi się komunikat o włączeniu workflows, kliknij "I understand my workflows, go ahead and enable them"

### 6. Testowanie lokalne (opcjonalne)

Jeśli chcesz przetestować skrypt lokalnie przed użyciem GitHub Actions:

```bash
# Zainstaluj Python 3.11+
python --version

# Stwórz virtual environment
python -m venv venv

# Aktywuj (Windows)
venv\Scripts\activate

# Aktywuj (Linux/Mac)
source venv/bin/activate

# Zainstaluj zależności
pip install -r requirements.txt

# Skopiuj .env.example do .env
cp .env.example .env

# Edytuj .env i wypełnij danymi
notepad .env  # Windows
nano .env     # Linux/Mac

# Uruchom synchronizację
python sync_garmin.py
```

Format `.env`:
```
GARMIN_EMAIL=your-email@example.com
GARMIN_PASSWORD=your-password
GOOGLE_SHEETS_CREDENTIALS={"type":"service_account",...}
```

## Użycie

### Automatyczna synchronizacja

GitHub Actions uruchomi synchronizację automatycznie:
- **6:00** czasu polskiego (rano)
- **18:00** czasu polskiego (wieczór)

### Ręczne uruchomienie

1. Przejdź do zakładki "Actions" w repozytorium
2. Wybierz workflow "Sync Garmin Activities"
3. Kliknij "Run workflow" → "Run workflow"

### Monitorowanie

- Logi synchronizacji: Actions → wybierz konkretne uruchomienie
- W przypadku błędu: sprawdź sekcję "Upload logs" w zakładce Artifacts

## Upload workoutów treningowych

### Przygotowanie planu

Stwórz plan treningowy w formacie Markdown (przykład: `plan/plan_treningowy_10km_38min.md`):

```markdown
### Tydzień 1 (40 km)
- **PON:** Odpoczynek + **Siła** (30 min)
- **WT:** Podbiegi 8x30s (tempo 5K, 90s zejście), 2 km R + 2 km WB = **6 km**
- **CZW:** BC2 8 km w Z2 (4:40-5:00/km) = **8 km**
- **SOB:** Tempo Run 2x10 min @ 4:05-4:10/km (3 min recovery) + 2 km R + 2 km WB = **9 km**
- **NIEDZ:** Długi bieg 17 km w Z2 (4:50-5:10/km) = **17 km**
```

### Upload do Garmin Connect

```bash
# Aktywuj virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate      # Windows

# Uruchom skrypt uploadu
python upload_workouts_to_garmin.py

# Wybierz opcję:
# 1 - Upload wszystkich treningów (bez schedulowania do kalendarza)
# 2 - Upload + scheduluj od dzisiejszej daty
# 3 - Upload + scheduluj od konkretnej daty
```

### Usuwanie workoutów

```bash
# Usuń wszystkie workouty z planu (które zaczynają się od "Tydzień")
python delete_all_workouts.py
```

### Format treningów

Parser rozpoznaje:
- **Podbiegi**: `8x30s (tempo 5K, 90s zejście)`
- **Interwały krótkie**: `8x400m @ 3:35-3:40/km (400m trucht)`
- **Długie interwały**: `4x2 km @ 3:50-3:55/km (400m trucht)`
- **Tempo run**: `2x10 min @ 4:05-4:10/km (3 min recovery)`
- **Długi bieg**: `17 km w Z2 (4:50-5:10/km)`

## Struktura projektu

```
garmin-training-sync/
├── .github/
│   └── workflows/
│       └── sync.yml                    # GitHub Actions workflow
├── plan/
│   └── plan_treningowy_10km_38min.md  # Plan treningowy (Markdown)
├── sync_garmin.py                      # Synchronizacja Garmin → Sheets
├── upload_workouts_to_garmin.py        # Upload workoutów do Garmin
├── delete_all_workouts.py              # Usuwanie workoutów
├── config.py                           # Konfiguracja (metryki, timezone)
├── requirements.txt                    # Zależności Python
├── .env.example                        # Przykładowy plik .env
├── .gitignore                          # Ignorowane pliki
└── README.md                           # Ten plik
```

## Konfiguracja zaawansowana

### Zmiana harmonogramu synchronizacji

Edytuj `.github/workflows/sync.yml`:

```yaml
schedule:
  # Zmień godziny (format: '0 GODZINA_UTC * * *')
  - cron: '0 5,17 * * *'  # 6:00 i 18:00 CET (UTC+1)
```

### Zmiana okresu synchronizacji

W `config.py`:

```python
# Zmień liczbę dni synchronizacji początkowej
INITIAL_SYNC_DAYS = 30  # Domyślnie 30 dni

# Synchronizacje kolejne zawsze pobierają ostatnie 2 dni
```

### Dodanie/usunięcie metryk

W `config.py`:

```python
# Dodaj metrykę do SHEET_HEADERS
SHEET_HEADERS = [
    'activity_id',
    'activity_type',
    # ... inne metryki
    'twoja_nowa_metryka',  # Dodaj tutaj
]
```

Następnie w `sync_garmin.py` w metodzie `process_activity()`:

```python
# Dodaj przetwarzanie metryki
processed['twoja_nowa_metryka'] = activity.get('garminfieldname')
```

### Zmiana strefy czasowej

W `config.py`:

```python
TIMEZONE = pytz.timezone('America/New_York')  # Przykład dla NY
```

## Rozwiązywanie problemów

### Błąd: "Failed to connect to Garmin"

- Sprawdź czy GARMIN_EMAIL i GARMIN_PASSWORD są poprawne w GitHub Secrets
- Garmin może wymagać zalogowania przez przeglądarkę (captcha) - zaloguj się ręcznie
- Spróbuj użyć hasła specyficznego dla aplikacji (jeśli Garmin to obsługuje)

### Błąd: "Failed to connect to Google Sheets"

- Sprawdź czy GOOGLE_SHEETS_CREDENTIALS zawiera poprawny JSON
- Upewnij się że Google Sheets API i Drive API są włączone
- Sprawdź czy arkusz jest udostępniony dla service account email

### Błąd: "Spreadsheet not found"

- Sprawdź czy nazwa arkusza to dokładnie `garmin_trainings`
- Lub zmień nazwę w `config.py`:
  ```python
  GOOGLE_SHEET_NAME = 'twoja_nazwa_arkusza'
  ```

### Duplikaty w arkuszu

Skrypt automatycznie pomija duplikaty na podstawie `activity_id`. Jeśli widzisz duplikaty:
- Usuń duplikaty ręcznie
- Uruchom synchronizację ponownie

### Brak niektórych metryk

Nie wszystkie metryki są dostępne dla wszystkich aktywności:
- Metryki biegowe (kadencja, GCT) tylko dla biegania
- Metryki mocy tylko dla kolarstwa z power metrem
- Niektóre metryki wymagają urządzeń Garmin z określonymi sensorami

## Bezpieczeństwo

- **NIE commituj** pliku `.env` ani credentials JSON
- Używaj GitHub Secrets dla wszystkich wrażliwych danych
- Repozytorium z danymi treningowymi ustaw jako Private
- Regularnie sprawdzaj czy service account nie ma zbędnych uprawnień

## Limitacje

- Garmin Connect API nie jest oficjalne - może ulec zmianie
- Google Sheets ma limit 5 milionów komórek na arkusz
- GitHub Actions ma limit 2000 minut/miesiąc na darmowym planie (ten projekt używa ~2 min/dzień = ~60 min/miesiąc)

## Rozwój projektu

### Planowane funkcje
- [ ] Obsługa wielu arkuszy (jeden na rok)
- [ ] Export do CSV jako backup
- [ ] Wizualizacje w Google Sheets (wykresy)
- [ ] Notyfikacje email przy błędach
- [ ] Dashboard z podsumowaniami

### Contributing

Pull requesty mile widziane! Przy większych zmianach otwórz najpierw Issue.

## Licencja

MIT License

## Autor

Projekt stworzony dla automatyzacji synchronizacji treningów Garmin.

## Podziękowania

- [garminconnect](https://github.com/cyberjunky/python-garminconnect) - Python library for Garmin Connect
- [gspread](https://github.com/burnash/gspread) - Google Sheets Python API

---

**Uwaga**: Ten projekt nie jest oficjalnie powiązany z Garmin ani Google.
