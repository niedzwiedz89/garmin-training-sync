# Konfiguracja środowiska wirtualnego (venv)

## 📍 Lokalizacja venv

**WAŻNE:** Venv jest przechowywany **LOKALNIE**, nie na Google Drive!

```
C:\venvs\garmin-training-sync\
```

**Dlaczego lokalnie?**
- ✅ Nie synchronizuje się przez Google Drive (oszczędność miejsca i czasu)
- ✅ Każde urządzenie ma swój venv (specyficzny dla systemu i wersji Python)
- ✅ ~8000 plików mniej do synchronizacji!

---

## 🚀 Instrukcje dla LAPTOPA FIRMOWEGO (mkozera)

### Krok 1: Utwórz folder dla venvs (jeśli nie istnieje)

```cmd
mkdir C:\venvs
```

### Krok 2: Utwórz venv

```cmd
python -m venv C:\venvs\garmin-training-sync
```

### Krok 3: Aktywuj venv i zainstaluj zależności

**PowerShell:**
```powershell
C:\venvs\garmin-training-sync\Scripts\Activate.ps1
cd C:\Users\mkozera\scripts\garmin-training-sync
pip install -r requirements.txt
```

**CMD:**
```cmd
C:\venvs\garmin-training-sync\Scripts\activate.bat
cd C:\Users\mkozera\scripts\garmin-training-sync
pip install -r requirements.txt
```

**Git Bash:**
```bash
source /c/venvs/garmin-training-sync/Scripts/activate
cd /c/Users/mkozera/scripts/garmin-training-sync
pip install -r requirements.txt
```

---

## 🏠 Instrukcje dla PRYWATNEGO PC (Michal)

### Krok 1: Poczekaj aż Google Drive zsynchronizuje projekt

Sprawdź czy folder istnieje:
```cmd
dir "C:\Users\Michal\scripts\garmin-training-sync"
```

### Krok 2: Utwórz folder dla venvs

```cmd
mkdir C:\venvs
```

### Krok 3: Utwórz venv

```cmd
python -m venv C:\venvs\garmin-training-sync
```

### Krok 4: Aktywuj venv i zainstaluj zależności

**PowerShell:**
```powershell
C:\venvs\garmin-training-sync\Scripts\Activate.ps1
cd C:\Users\Michal\scripts\garmin-training-sync
pip install -r requirements.txt
```

**CMD:**
```cmd
C:\venvs\garmin-training-sync\Scripts\activate.bat
cd C:\Users\Michal\scripts\garmin-training-sync
pip install -r requirements.txt
```

**Git Bash:**
```bash
source /c/venvs/garmin-training-sync/Scripts/activate
cd /c/Users/Michal/scripts/garmin-training-sync
pip install -r requirements.txt
```

---

## 💻 Używanie venv

### Aktywacja venv (przed pracą)

**PowerShell:**
```powershell
C:\venvs\garmin-training-sync\Scripts\Activate.ps1
```

**CMD:**
```cmd
C:\venvs\garmin-training-sync\Scripts\activate.bat
```

**Git Bash:**
```bash
source /c/venvs/garmin-training-sync/Scripts/activate
```

Po aktywacji zobaczysz `(garmin-training-sync)` przed promptem.

### Uruchamianie skryptów

```cmd
# Po aktywacji venv:
cd C:\Users\[TWOJA_NAZWA]\scripts\garmin-training-sync
python sync_garmin.py
```

Lub bez aktywacji (pełna ścieżka):
```cmd
C:\venvs\garmin-training-sync\Scripts\python.exe sync_garmin.py
```

### Deaktywacja venv

```cmd
deactivate
```

---

## 🔧 Konfiguracja IDE

### Visual Studio Code

1. Otwórz folder projektu w VS Code
2. `Ctrl+Shift+P` → wpisz: "Python: Select Interpreter"
3. Wybierz: `C:\venvs\garmin-training-sync\Scripts\python.exe`
4. Jeśli nie ma na liście, kliknij "Enter interpreter path" i wskaż:
   ```
   C:\venvs\garmin-training-sync\Scripts\python.exe
   ```

**Ustawienie w workspace (opcjonalnie):**

Utwórz `.vscode/settings.json` w projekcie:
```json
{
    "python.defaultInterpreterPath": "C:\\venvs\\garmin-training-sync\\Scripts\\python.exe",
    "python.terminal.activateEnvironment": true
}
```

### PyCharm

1. `File` → `Settings` (lub `Ctrl+Alt+S`)
2. `Project: garmin-training-sync` → `Python Interpreter`
3. Kliknij ⚙️ → `Add Interpreter` → `Add Local Interpreter`
4. `Existing environment`
5. Wskaż: `C:\venvs\garmin-training-sync\Scripts\python.exe`
6. Kliknij `OK`

### Jupyter Notebook

Jeśli używasz Jupyter:

```cmd
# Aktywuj venv
C:\venvs\garmin-training-sync\Scripts\activate.bat

# Zainstaluj ipykernel
pip install ipykernel

# Zarejestruj venv jako kernel
python -m ipykernel install --user --name=garmin-training-sync --display-name="Garmin Sync"

# Uruchom Jupyter
jupyter notebook
```

W Jupyter wybierz kernel: "Garmin Sync"

---

## 🔄 Aktualizacja zależności

Gdy ktoś doda nowe pakiety do `requirements.txt`:

### Na urządzeniu gdzie pracujesz:

1. Aktywuj venv
2. Zainstaluj nowe pakiety:
   ```cmd
   pip install -r requirements.txt
   ```

### Na drugim urządzeniu:

1. Poczekaj aż Google Drive zsynchronizuje `requirements.txt`
2. Aktywuj venv
3. Zaktualizuj pakiety:
   ```cmd
   pip install -r requirements.txt
   ```

---

## 🐛 Rozwiązywanie problemów

### Problem: "python nie jest rozpoznawany jako polecenie"

**Rozwiązanie:**
1. Sprawdź czy Python jest zainstalowany: `python --version`
2. Jeśli nie, zainstaluj Python z [python.org](https://www.python.org/downloads/)
3. Podczas instalacji zaznacz "Add Python to PATH"

### Problem: "Nie mogę aktywować venv w PowerShell"

**Błąd:**
```
... cannot be loaded because running scripts is disabled on this system
```

**Rozwiązanie:**
Uruchom PowerShell jako Administrator i wykonaj:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problem: "pip: command not found"

**Rozwiązanie:**
Użyj pełnej ścieżki:
```cmd
C:\venvs\garmin-training-sync\Scripts\python.exe -m pip install -r requirements.txt
```

### Problem: "ModuleNotFoundError" po uruchomieniu skryptu

**Rozwiązanie:**
1. Upewnij się że venv jest aktywowany (widać `(garmin-training-sync)`)
2. Sprawdź czy pakiety są zainstalowane:
   ```cmd
   pip list
   ```
3. Jeśli brakuje, zainstaluj:
   ```cmd
   pip install -r requirements.txt
   ```

### Problem: "Venv zajmuje dużo miejsca"

To normalne! Venv może zajmować 200-500 MB.

**Czyszczenie niepotrzebnych venvs:**
```cmd
# Lista folderów w C:\venvs
dir C:\venvs

# Usuń stary venv
rmdir /s C:\venvs\stary-projekt
```

### Problem: "Chcę przenieść venv w inne miejsce"

**Nie da się!** Venv ma zakodowane ścieżki absolutne.

**Rozwiązanie:**
1. Usuń stary venv
2. Utwórz nowy w nowej lokalizacji
3. Zainstaluj zależności ponownie

---

## 📦 Dodawanie nowych pakietów

### Krok 1: Zainstaluj pakiet

```cmd
pip install nazwa-pakietu
```

### Krok 2: Zaktualizuj requirements.txt

```cmd
pip freeze > requirements.txt
```

Lub dodaj ręcznie do `requirements.txt`:
```
nazwa-pakietu>=X.X.X
```

### Krok 3: Commit i push (jeśli to repo Git)

```cmd
git add requirements.txt
git commit -m "Add: nazwa-pakietu"
git push
```

### Krok 4: Na drugim urządzeniu

```cmd
git pull
pip install -r requirements.txt
```

---

## 🎯 Workflow (jak pracować z synchronizacją)

### Przed rozpoczęciem pracy:

1. **Sprawdź synchronizację Google Drive** (ikona w zasobniku)
2. **Git pull** (jeśli to repo):
   ```cmd
   cd C:\Users\[NAZWA]\scripts\garmin-training-sync
   git pull
   ```
3. **Aktywuj venv:**
   ```cmd
   C:\venvs\garmin-training-sync\Scripts\activate
   ```
4. **Aktualizuj zależności** (jeśli `requirements.txt` się zmienił):
   ```cmd
   pip install -r requirements.txt
   ```

### Po zakończeniu pracy:

1. **Commit zmiany** (jeśli to repo):
   ```cmd
   git add .
   git commit -m "opis zmian"
   git push
   ```
2. **Poczekaj na synchronizację Google Drive** (30-60 sekund)
3. **Deaktywuj venv** (opcjonalnie):
   ```cmd
   deactivate
   ```

### ⚠️ ZASADY:

- **NIGDY nie pracuj jednocześnie na obu urządzeniach!**
- Zawsze rób `git pull` przed pracą
- Zawsze rób `git push` po zakończeniu
- Poczekaj na synchronizację Google Drive między przełączeniami

---

## 📊 Struktura projektu

```
C:\Users\[NAZWA]\scripts\garmin-training-sync\  ← Symlink do Google Drive
├── sync_garmin.py                              ← Skrypty (synchronizowane)
├── requirements.txt                            ← Zależności (synchronizowane)
├── .git\                                       ← Git repo (synchronizowane)
├── .gitignore                                  ← Ignoruje venv (synchronizowane)
└── VENV_SETUP.md                               ← Ten plik (synchronizowany)

C:\venvs\garmin-training-sync\                  ← Venv (LOKALNY, nie synchronizowany!)
├── Scripts\
│   ├── python.exe
│   ├── pip.exe
│   └── activate.bat
└── Lib\
    └── site-packages\
        └── ... (8000+ plików pakietów)
```

---

## ℹ️ Dodatkowe informacje

### Wersje Python:

- **Laptop firmowy:** Python 3.13.7
- **Prywatny PC:** [sprawdź: `python --version`]

Jeśli wersje się różnią, to OK! Każde urządzenie ma swój venv dostosowany do swojej wersji.

### Alternatywy dla venv:

Jeśli masz wiele projektów Python, rozważ:

- **[Poetry](https://python-poetry.org/):** Zarządzanie zależnościami + venv automatycznie
- **[Pipenv](https://pipenv.pypa.io/):** Podobne do Poetry
- **[Conda](https://docs.conda.io/):** Jeśli pracujesz z data science

### Dokumentacja:

- [Python venv](https://docs.python.org/3/library/venv.html)
- [pip documentation](https://pip.pypa.io/)
- [requirements.txt](https://pip.pypa.io/en/stable/reference/requirements-file-format/)

---

## 📅 Historia zmian

- **2025-11-06:** Pierwotna konfiguracja - venv przeniesiony z projektu do C:\venvs\
- **Laptop firmowy:** Python 3.13.7, wszystkie zależności zainstalowane ✅
- **Prywatny PC:** Oczekuje na konfigurację

---

**Pytania? Problemy?**

Sprawdź sekcję "Rozwiązywanie problemów" powyżej lub przeczytaj oficjalną dokumentację Python venv.

**Powodzenia! 🚀**
