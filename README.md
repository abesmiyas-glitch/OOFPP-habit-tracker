# Habit Tracker

A Python backend for a habit-tracking application built with object-oriented programming for the domain model
and functional programming for analytics, an SQLite database for persistence, and an
interactive command-line interface (entry point).

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Database Setup](#database-setup)
5. [Running the Application](#running-the-application)
6. [Predefined Habits & Fixture Data](#predefined-habits--fixture-data)
7. [Creating Habits](#creating-habits)
8. [Editing a Habit](#editing-a-habit)
9. [Completing a Task](#completing-a-task)
10. [Analytics](#analytics)
11. [Running the Tests](#running-the-tests)
12. [Module Reference](#module-reference)

---

## Project Structure

```
habit_tracker/
├── habit.py                # Habit class (OOP core)
├── analytics.py            # Analytics module (functional programming)
├── storage.py              # SQLite persistence layer
├── seed_data.py            # Predefined habits + 4-week fixture data
├── cli.py                  # Interactive command-line interface
├── test_habit_tracker.py   # Unit test suite (106 tests)
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
└── README.md               # This file
```

---

## Requirements

### Option A — Docker (recommended, no local Python setup needed)
- [Docker Desktop](https://www.docker.com/products/docker-desktop)

That's it. Python, rich, pytest, and all other dependencies are handled inside the container.

### Option B — Run locally without Docker
- Python **3.7 or later**
- `rich` — for the styled CLI interface
- `pytest` *(optional)* — for a nicer test runner; `unittest` works without it
- `sqlite3` — bundled with every standard CPython installation

---

## Installation

### Option A — Docker (recommended)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop) and make sure it is running.

2. Clone or download this repository so that all files sit in the same directory.

3. Build the image (one-time step):

   ```bash
   docker build --no-cache -t habit-tracker .
   ```

That's all. Skip to [Running the Application](#running-the-application).

### Option B — Local Python

1. **Clone or download** this repository so that all files sit in the same directory.

2. **Verify your Python version**:

   ```bash
   python --version   # must be 3.7+
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

---


## Database Setup

The application uses SQLite for persistence. The database file (`habits.db`) is
created automatically on first run — no manual setup is required.

### How it works

- `habits.db` is created in the current directory when you run `python cli.py`
- When using Docker with a volume, it is created at `/app/data/habits.db`
  inside the container, mapped to `./data/habits.db` on your machine
- The schema (tables) is initialised automatically on every startup via
  `initialise_db()` — this is safe to run multiple times

### Seed data

To pre-populate the database with 5 sample habits and 4 weeks of example
tracking data anchored to today's date:

```bash
# Local
python cli.py --seed

# Docker
docker run -it habit-tracker --seed
```

> ⚠️ `--seed` always overwrites existing sample habits with fresh data
> anchored to today. Any habits you created manually are not affected.

### Resetting the database

To start completely fresh:

```bash
# Windows
del habits.db

# Mac / Linux
rm habits.db
```

Then run the app again. Use `--seed` if you want the sample data back.

### Important — do not commit the database

`habits.db` is listed in `.gitignore` and should never be pushed to the
repository. Anyone cloning the project gets a clean slate and generates
their own database on first run.

---

## Running the Application

### With Docker

```bash
# With sample habits pre-loaded (recommended first run)
docker run -it habit-tracker --seed

# Without sample data
docker run -it habit-tracker

# Persist data between container runs (habits survive after the container stops)
docker run -it -v "$(pwd)/data:/app/data" habit-tracker
```

> **Windows note:** if `$(pwd)` causes issues in PowerShell, use the full path instead:
> `docker run -it -v "C:\path\to\project\data:/app/data" habit-tracker`

### Without Docker

```bash
# With sample habits pre-loaded (recommended first run)
python cli.py --seed

# Without sample data
python cli.py
```

### Interactive Menu

```
╔══════════════════════════════════════╗
║         HABIT TRACKER MENU           ║
╠══════════════════════════════════════╣
║  1  List all habits                  ║
║  2  Filter habits                    ║
║  3  Create a habit                   ║
║  4  Edit a habit                     ║
║  5  Complete a habit                 ║
║  6  Delete a habit                   ║
║  7  Longest streak among all habits  ║
║  8  Longest streak of a habit        ║
║  9  Most struggled habits            ║
║  10 Habit details                    ║
║  0  Quit                             ║
╚══════════════════════════════════════╝
```

Type the number and press **Enter** to select an option.

---

## Predefined Habits & Fixture Data

Running with `--seed` loads five habits with 4 weeks of example tracking data:

| Name                 | Periodicity | Description                                         |
|----------------------|-------------|-----------------------------------------------------|
| `morning_meditation` | daily       | Meditate for 10 minutes after waking up             |
| `drink_water`        | daily       | Drink at least 2 litres of water throughout the day |
| `read`               | daily       | Read at least 10 pages of a book                    |
| `exercise`           | daily       | Complete 30 minutes of physical exercise            |
| `meal_prep`          | weekly      | Plan and prepare meals for the coming week          |

Each habit has realistic completion patterns (with missed completions) so that
streak and analytics features can be meaningfully demonstrated.

The fixture data is defined in `seed_data.py` and covers the 4-week period
ending today. The seed function is idempotent — running it again skips habits
that already exist.

---

## Creating Habits

**Via the CLI (menu option 3):**

1. Start the app: `python cli.py` or `docker run -it habit-tracker`
2. Choose option `3`
3. Enter a unique name (e.g. `journal`)
4. Enter a description (e.g. `Write in journal for 5 minutes`)
5. Choose `d` for daily or `w` for weekly (daily by default)

**Programmatically:**

```python
from habit import Habit
from storage import initialise_db, save_habit

DB = "habits.db"
initialise_db(DB)

new_habit = Habit(
    name="journal",
    description="Write in journal for 5 minutes",
    periodicity="daily",   # or "weekly"
)
save_habit(new_habit, DB)
```

Valid periodicity values are `"daily"` and `"weekly"`. Any other value raises a `ValueError`.

---

## Editing a Habit

**Via the CLI (menu option 4):**

1. Choose option `4`
2. Select the habit by number
3. Press Enter to keep the current description, or type a new one
4. Press Enter to keep the current periodicity, or type `d` / `w` to change it

> ⚠️ Changing the periodicity clears all existing completions 
> ⚠️ daily timestamps are meaningless in a weekly streak context.

**Programmatically:**

```python
from storage import load_all_habits, save_habit

habits = load_all_habits("habits.db")
h = next(h for h in habits if h.name == "journal")

# Update description only — completions are preserved
h.description = "Write in journal for 10 minutes"
save_habit(h, "habits.db")

# Update periodicity — must clear completions first
h.periodicity = "weekly"
h.completions.clear()
save_habit(h, "habits.db")
```

---

## Completing a Task

**Via the CLI (menu option 5):**

1. Choose option `5`
2. Select the habit by number
3. Press Enter to use the current time, or type a custom datetime in the
   format `YYYY-MM-DD HH:MM`

**Programmatically:**

```python
from datetime import datetime
from storage import load_all_habits, save_habit

habits = load_all_habits("habits.db")
h = next(h for h in habits if h.name == "journal")

# Complete now
h.complete()

# Complete at a specific time
h.complete(datetime(2024, 6, 15, 21, 30))

save_habit(h, "habits.db")   # persist the new completion
```

A habit can be completed multiple times in one period; only the **first**
completion per period counts towards the streak.

---

## Analytics

The `analytics` module exposes the following pure functions:

```python
from analytics import (
    get_all_habits,               # List all habits
    get_habits_by_periodicity,    # Filter by 'daily' or 'weekly'
    get_longest_streak_all,       # (habit, streak) with best overall streak
    get_longest_streak_for_habit, # Longest streak for one habit
    get_struggle_habits,          # Habits ranked by missed periods
    habit_summary,                # Summary of one habit
)
from storage import load_all_habits

habits = load_all_habits("habits.db")

# All habits (option 1)
print(get_all_habits(habits))

# Daily habits only (option 2)
print(get_habits_by_periodicity(habits, "daily"))

# Habit with the longest ever streak (option 7)
best, streak = get_longest_streak_all(habits)
print(f"{best.name}: {streak} periods")

# Longest streak for a specific habit (option 8)
h = habits[0]
print(get_longest_streak_for_habit(h))

# Habits you struggle with most (most missed periods first) (option 9)
for habit, missed in get_struggle_habits(habits):
    print(f"{habit.name}: {missed} missed periods")
```

---

## Running the Tests

The test suite uses Python's built-in `unittest` (106 tests covering all modules).

### With Docker (recommended)

```bash
docker run --rm --entrypoint python habit-tracker -m unittest test_habit_tracker -v
```

### Without Docker

```bash
# Using unittest (no install required)
python -m unittest test_habit_tracker -v

# Using pytest (if installed)
python -m pytest test_habit_tracker.py -v
```

Expected output ends with:

```
Ran 106 tests in <time>s

OK
```

Test areas covered:

- `TestHabitCreation` — Habit init and validation
- `TestHabitCompletion` — check-off recording, ordering, and period deduplication
- `TestPeriodKeys` — daily and weekly period key generation and edge cases
- `TestStreaks` — current and longest streak logic for daily and weekly habits
- `TestSerialisation` — `to_dict` / `from_dict` round-trip for all habit types
- `TestAnalytics` — all analytics functions including empty-list edge cases
- `TestStorage` — SQLite save, load, delete, exists, and data integrity
- `TestSeedData` — fixture data correctness, idempotency, and overwrite behaviour
- `TestEditHabit` — edit description, edit periodicity, completions cleared on period change

---

## Module Reference

### `habit.py` — `Habit` class

| Method / Attribute | Description |
|---|---|
| `Habit(name, description, periodicity, created_at=None)` | Create a new habit |
| `.complete(when=None)` | Record a completion; defaults to now |
| `.completed_periods()` | Sorted list of unique period keys with a completion |
| `.current_streak()` | Consecutive-period streak ending today/this week |
| `.longest_streak()` | Best-ever consecutive-period streak |
| `.to_dict()` | Serialise to a plain dict |
| `Habit.from_dict(data)` | Deserialise from a dict |

### `analytics.py` — functional analytics

All functions are pure (no side effects).

| Function | Returns |
|---|---|
| `get_all_habits(habits)` | List of all habits |
| `get_habits_by_periodicity(habits, period)` | Filtered list |
| `get_longest_streak_all(habits)` | `(Habit, int)` best streak pair |
| `get_longest_streak_for_habit(habit)` | `int` longest streak |
| `get_struggle_habits(habits, since=None)` | `[(Habit, int)]` sorted by missed periods |
| `habit_summary(habit)` | `dict` with key stats |

### `storage.py` — SQLite persistence

| Function | Description |
|---|---|
| `initialise_db(db_path)` | Create tables if they don't exist |
| `save_habit(habit, db_path)` | Insert or update a habit + completions |
| `load_all_habits(db_path)` | Return all habits with completions |
| `delete_habit(name, db_path)` | Delete a habit; returns `bool` |
| `habit_exists(name, db_path)` | Check existence; returns `bool` |

### `seed_data.py` — fixture data

| Function | Description |
|---|---|
| `seed_database(db_path, overwrite=False)` | Insert 5 predefined habits; returns list of inserted names |

### `cli.py` — command-line interface

```bash
# Local
python cli.py          # interactive menu, empty database
python cli.py --seed   # pre-populate with 5 sample habits

# Docker
docker run -it habit-tracker          # interactive menu, empty database
docker run -it habit-tracker --seed   # pre-populate with 5 sample habits
```

## Troubleshooting

### Seed data shows stale dates or current streak is 0

The seed data anchors all completions to today's date at runtime. In some cases, If you ran
`--seed` on a previous date, the database still holds those old completions.

**Without Docker — delete the local database and reseed:**
```bash
# Windows
del habits.db

# Mac / Linux
rm habits.db
```
Then reseed:
```bash
python cli.py --seed
```

**With Docker (no volume) — the database lives inside the container. Just run
`--seed` again, which always overwrites with fresh dates:**
```bash
docker run -it habit-tracker --seed
```

**With Docker and a volume — delete the database file from your local data folder:**
```bash
# Windows
del data\habits.db

# Mac / Linux
rm data/habits.db
```
Then reseed:
```bash
docker run -it -v "$(pwd)/data:/app/data" habit-tracker --seed
```