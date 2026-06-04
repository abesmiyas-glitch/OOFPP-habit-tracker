"""
analytics.py

The analytics class defines the core of functional programming.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from habit import Habit


# Basic Functions

def get_all_habits(habits: List[Habit]) -> List[Habit]:
    """
    Return a list of all currently tracked habits.

    Args:
        habits: Master list of :class:`~habit.Habit` objects.

    Returns:
        An unsorted list containing all tracked habit.
    """
    return list(habits)


def get_habits_by_periodicity(habits: List[Habit], periodicity: str) -> List[Habit]:
    """
    Return all habits whose periodicity matches the given value (either weekly OR daily).

    Args:
        habits:      Master list of habits.
        periodicity: ``'daily'`` or ``'weekly'``.

    Returns:
        Filtered list of matching habits.
    """
    return list(filter(lambda h: h.periodicity == periodicity, habits))



# Streak analytics


def get_longest_streak_all(habits: List[Habit]) -> Tuple[Optional[Habit], int]:
    """
    Return the habit with the longest ever streak among all habits and that streak length.

    When multiple habits share the same longest streak the first one
    encountered (in the order of *habits*) is returned.

    Args:
        habits: list of habits.

    Returns:
        A ``(habit, streak_length)`` tuple.  
        Special case : If *habits* is empty the habit
        element is ``None`` and the streak length is ``0``.
    """
    if not habits:
        return (None, 0)

    scored = map(lambda h: (h, h.longest_streak()), habits)
    best = max(scored, key=lambda pair: pair[1])
    return best


def get_longest_streak_for_habit(habit: Habit) -> int:
    """
    Return the longest ever streak for a single habit.

    Args:
        habit: The chosen habit.

    Returns:
        Integer streak length (0 if the habit was never completed).
    """
    return habit.longest_streak()



# Struggle / difficulty analytics


def get_struggle_habits(
    habits: List[Habit],
    since: Optional[datetime] = None,
) -> List[Tuple[Habit, int]]:
    """
    Return habits ranked by the number of periods in which the user broke
    the habit (failed to complete it).
    The most broken one is ranked first.

    A broken period is counted when a period falls between the habit's
    creation date and *since* (exclusive) and contains no completion.

    Args:
        habits: list of habits.
        since:  Only consider periods up to but not including this datetime.
                Defaults to ``datetime.now()``.

    Returns:
        List of ``(habit, broken_count)`` tuples sorted descending by
        ``broken_count``.  Habits with zero broken periods are also included.
    """
    cutoff = since or datetime.now()

    def broken_count(habit: Habit) -> int:
        """Counts how many periods had no completion between creation and cutoff."""
        completed = set(habit.completed_periods())
        all_periods = _all_periods_between(habit, cutoff)
        missed = filter(lambda p: p not in completed, all_periods)
        return sum(1 for _ in missed)

    scored = map(lambda h: (h, broken_count(h)), habits)
    return sorted(scored, key=lambda pair: pair[1], reverse=True)


def _all_periods_between(habit: Habit, cutoff: datetime) -> List[tuple]:
    """
    Generate all period keys from the habit's creation date up to cutoff.

    This is a helper for :func:`get_struggle_habits`.

    Args:
        habit:  The habit whose creation date sets the start.
        cutoff: Upper boundary (exclusive of the period containing cutoff).

    Returns:
        Sorted list of period key tuples.
    """
    from datetime import timedelta, date

    periods: List[tuple] = []
    cursor = habit.created_at

    if habit.periodicity == "daily":
        step = timedelta(days=1)
        while cursor < cutoff:
            periods.append((cursor.year, cursor.month, cursor.day))
            cursor += step
    else:  # weekly
        # Start from the Monday of the week the habit was created
        creation_date = habit.created_at.date()
        monday = creation_date - timedelta(days=creation_date.weekday())
        week_cursor = monday
        cutoff_date = cutoff.date()
        while week_cursor < cutoff_date:
            iso = week_cursor.isocalendar()
            periods.append((iso[0], iso[1]))
            week_cursor += timedelta(weeks=1)

    return periods


# Convenience summary


def habit_summary(habit: Habit) -> dict:
    """
    Build a summary dictionary for a single habit.

    The summary includes the creation timestamp, all completion datetimes (date and time),
    and streak statistics, users can track when the habit was created and when each task was completed.
    

    Args:
        habit: The habit to summarise.

    Returns:
        Dictionary with keys: name, description, periodicity, created_at,
        total_completions, current_streak, longest_streak, completion_history.
    """
    return {
        "name":               habit.name,
        "description":        habit.description,
        "periodicity":        habit.periodicity,
        "created_at":         habit.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "total_completions":  len(habit.completions),
        "current_streak":     habit.current_streak(),
        "longest_streak":     habit.longest_streak(),
        "completion_history": [
            ts.strftime("%Y-%m-%d %H:%M:%S") for ts in habit.completions
        ],
    }
