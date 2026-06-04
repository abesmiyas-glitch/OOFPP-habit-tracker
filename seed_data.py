"""
seed_data.py

Predefined habits and 4-week example tracking data used as test fixtures.

Call :func:`seed_database` to populate a fresh (or existing) database with
the five predefined habits.  

Any habit whose name already exists in the database is *skipped* so that the 
function is safe to call multiple times.
This ensures that running the function multiple times does not create duplicates,
making it idempotent to call on every application startup or setup.

Predefined habits

Daily:
    1. morning_meditation  – Meditate for 10 minutes after waking up
    2. drink_water         – Drink at least 2 litres of water
    3. read                – Read at least 10 pages of a book
    4. exercise            – 30 minutes of physical exercise

Weekly:
    5. meal_prep           – Plan and prepare meals for the coming week
"""

from datetime import datetime, timedelta
from typing import List

from habit import Habit
from storage import save_habit, habit_exists


# Fixture builder helpers

def _daily_completions(
    start: datetime,
    days: int,
    miss_days: List[int] = None,
) -> List[datetime]:
    """
    Build a list of daily completion timestamps for *x days* consecutive days
    starting from *start*, skipping any day index listed in *miss_days*.

    Args:
        start:     First possible completion date.
        days:      Total number of days to consider.
        miss_days: 0-based indices of days to leave incomplete.

    Returns:
        List of datetime objects (one per completed day).
    """
    miss_days = miss_days or []
    completions = []
    for i in range(days):
        if i not in miss_days:
            completions.append(start + timedelta(days=i, hours=8))
    return completions


def _weekly_completions(
    start: datetime,
    weeks: int,
    miss_weeks: List[int] = None,
) -> List[datetime]:
    """
    Build a list of weekly completion timestamps for *y weeks* consecutive weeks.

    Args:
        start:      Monday of the first week.
        weeks:      Total number of weeks.
        miss_weeks: 0-based indices of weeks to leave incomplete.

    Returns:
        List of datetime objects (one per completed week).
    """
    miss_weeks = miss_weeks or []
    completions = []
    for i in range(weeks):
        if i not in miss_weeks:
            completions.append(start + timedelta(weeks=i, days=2, hours=10))
    return completions


# Predefined habits

def _build_predefined_habits() -> List[Habit]:
    """
    Construct the five predefined Habit objects with 4-week fixture data.

    Completions are anchored relative to today so that current streaks
    are always active when the sample data is loaded.

    The start date is 28 days before today. Completions run all the way
    up to and including today (from day 0 to day 27),
    so that current_streak() returns a non-zero
    value for every habit that has no miss on the final day (today).

    Returns:
        List of five Habit instances.
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=27)   # 28 days total: day 0 .. day 27 = today

    # Number of days from start to today inclusive (4 weeks)
    total_days = 28

    
    # 1. Morning meditation (daily)
    #    Misses day 10 and day 17 — two streak breaks
    #    Last day (27 = today) is completed → current streak active
    
    meditation = Habit(
        name="morning_meditation",
        description="Meditate for 10 minutes after waking up",
        periodicity="daily",
        created_at=start,
    )
    for ts in _daily_completions(start, total_days, miss_days=[10, 17]):
        meditation.completions.append(ts)

    
    # 2. Drink water (daily) – perfect streak all 28 days including today
    
    water = Habit(
        name="drink_water",
        description="Drink at least 2 litres of water throughout the day",
        periodicity="daily",
        created_at=start,
    )
    for ts in _daily_completions(start, total_days, miss_days=[]):
        water.completions.append(ts)

    
    # 3. Read (daily) – misses days 5, 6, 7 and day 20
    #    Completed today → current streak active
    
    read = Habit(
        name="read",
        description="Read at least 10 pages of a book",
        periodicity="daily",
        created_at=start,
    )
    for ts in _daily_completions(start, total_days, miss_days=[5, 6, 7, 20]):
        read.completions.append(ts)

    
    # 4. Exercise (daily) – misses days 0, 7, 14, 21 (every Monday)
    #    Today is not a Monday in most cases → current streak active
    
    exercise = Habit(
        name="exercise",
        description="Complete 30 minutes of physical exercise",
        periodicity="daily",
        created_at=start,
    )
    # Calculate which day index today falls on to avoid missing today
    today_idx = (today - start).days   # should be 27
    monday_misses = [i for i in [0, 7, 14, 21] if i != today_idx]
    for ts in _daily_completions(start, total_days, miss_days=monday_misses):
        exercise.completions.append(ts)

    
    # 5. Meal prep (weekly) – 4 weeks, misses week 2 (index 1)
    #    Week 3 (index 3) covers this week → current streak active
    
    # Start from Monday of the week 4 weeks ago
    days_since_monday = today.weekday()
    this_monday = today - timedelta(days=days_since_monday)
    week_start  = this_monday - timedelta(weeks=3)

    meal_prep = Habit(
        name="meal_prep",
        description="Plan and prepare meals for the coming week",
        periodicity="weekly",
        created_at=week_start,
    )
    for ts in _weekly_completions(week_start, 4, miss_weeks=[1]):
        meal_prep.completions.append(ts)

    return [meditation, water, read, exercise, meal_prep]



# Public API


def seed_database(db_path: str, overwrite: bool = False) -> List[str]:
    """
    Populate *db_path* with the five predefined habits and their fixture data.

    Args:
        db_path:   Path to the SQLite database (must already be initialised).
        overwrite: If True, existing habits are replaced; if False (default)
                   any habit whose name already exists is skipped.

    Returns:
        List of habit names that were actually inserted (or replaced).
    """
    habits = _build_predefined_habits()
    inserted = []

    for habit in habits:
        if not overwrite and habit_exists(habit.name, db_path):
            continue
        save_habit(habit, db_path)
        inserted.append(habit.name)

    return inserted
