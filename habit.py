"""
habit.py

The Habit class defines the habit data and behavior, the core of the habit tracker.
"""

from datetime import datetime, date
from typing import List, Optional


class Habit:
    """
    Represents a single habit with a task description, periodicity, and
    a log of completion timestamps.

    Attributes:
        name (str): A short, unique name for the habit (used as identifier).
        description (str): A description of the task.
        periodicity (str): Either 'daily' or 'weekly'.
        created_at (datetime): When the habit was first created.
        completions (List[datetime]): Sorted list of datetime objects recording
            every time the habit task was checked off.
    """

    VALID_PERIODS = ("daily", "weekly")

    def __init__(
        self,
        name: str,
        description: str,
        periodicity: str,
        created_at: Optional[datetime] = None,
    ):
        """
        Initialise a new Habit.

        Args:
            name: Unique identifier / short label for the habit.
            description: What the user has to do each period.
            periodicity: 'daily' or 'weekly'.
            created_at: Creation timestamp; defaults to now if omitted.

        Raises:
            ValueError: If periodicity is not 'daily' or 'weekly'.
        """
        if periodicity not in self.VALID_PERIODS:
            raise ValueError(
                f"periodicity must be one of {self.VALID_PERIODS}, got {periodicity!r}"
            )
        self.name = name
        self.description = description
        self.periodicity = periodicity
        self.created_at: datetime = created_at or datetime.now()
        self.completions: List[datetime] = []

    
    # Completion helpers
    

    def complete(self, when: Optional[datetime] = None) -> datetime:
        """
        Record a completion of the habit task.

        Args:
            when: Either a datetime of completion; OR defaults to now.

        Returns:
            The datetime that was recorded.
        """
        ts = when or datetime.now()
        self.completions.append(ts)
        self.completions.sort()
        return ts

    
    # Period helpers
    

    def _period_key(self, dt: datetime) -> tuple:
        """
        Return a hashable key that uniquely identifies the period a datetime
        belongs to.

        For daily habits  → (year, month, day)
        For weekly habits → (ISO year, ISO week number)
        """
        if self.periodicity == "daily":
            return (dt.year, dt.month, dt.day)
        # weekly: use ISO calendar so week boundaries are consistent
        iso = dt.isocalendar()
        return (iso[0], iso[1])  # (iso_year, iso_week)

    def completed_periods(self) -> List[tuple]:
        """
        Return a deduplicated (Repeated completions in a single period are removed), sorted list of period keys in which 
        the habit was completed at least once.
        """
        seen = set()
        periods = []
        for ts in self.completions:
            key = self._period_key(ts)
            if key not in seen:
                seen.add(key)
                periods.append(key)
        return sorted(periods)

    
    # Streak calculation
    

    def _consecutive_periods(self, period_keys: List[tuple]) -> List[List[tuple]]:
        """
        Group a sorted list of period keys into runs of consecutive periods.

        Two period keys are consecutive when the second immediately follows
        the first according to the habit's periodicity.

        Args:
            period_keys: Sorted list of unique period keys.

        Returns:
            List of groups, where each group is a list of consecutive keys.
        """
        if not period_keys:
            return []

        groups: List[List[tuple]] = [[period_keys[0]]]

        for key in period_keys[1:]:
            prev = groups[-1][-1]
            if self._are_consecutive(prev, key):
                groups[-1].append(key)
            else:
                groups.append([key])

        return groups

    def _are_consecutive(self, a: tuple, b: tuple) -> bool:
        """
        Return True if period key *b* directly follows period key *a*.

        For daily periods the keys are (year, month, day) tuples, so we
        convert to date objects and check that the gap is exactly one day.

        For weekly periods the keys are (iso_year, iso_week) tuples; we
        convert to the Monday of each week and check for a 7-day gap.
        """
        if self.periodicity == "daily":
            date_a = date(*a)
            date_b = date(*b)
            return (date_b - date_a).days == 1
        else:  # weekly
            # Monday of ISO week: use date.fromisocalendar 
            try:
                mon_a = date.fromisocalendar(a[0], a[1], 1)
                mon_b = date.fromisocalendar(b[0], b[1], 1)
            except AttributeError:
                # Fallback for Python 3.7
                import datetime as _dt
                def _iso_to_date(iso_year, iso_week):
                    jan4 = _dt.date(iso_year, 1, 4)
                    monday = jan4 - _dt.timedelta(days=jan4.weekday())
                    return monday + _dt.timedelta(weeks=iso_week - 1)
                mon_a = _iso_to_date(*a)
                mon_b = _iso_to_date(*b)
            return (mon_b - mon_a).days == 7

    def current_streak(self) -> int:
        """
        Return the length of the current (most recent) streak in periods.

        The streak is 0 if the habit has never been completed or if the most
        recent period with a completion is not the current period (i.e., the
        habit was broken before today / this week).
        """
        periods = self.completed_periods()
        if not periods:
            return 0

        today_key = self._period_key(datetime.now())
        if periods[-1] != today_key:
            return 0

        groups = self._consecutive_periods(periods)
        return len(groups[-1]) if groups else 0

    def longest_streak(self) -> int:
        """
        Return the longest streak ever achieved for this habit (in periods either days / weeks).
        """
        periods = self.completed_periods()
        if not periods:
            return 0
        groups = self._consecutive_periods(periods)
        return max(len(g) for g in groups)

    
    # Serialisation
    

    def to_dict(self) -> dict:
        """Serialise the habit to a plain dictionary (for JSON / DB storage)."""
        return {
            "name": self.name,
            "description": self.description,
            "periodicity": self.periodicity,
            "created_at": self.created_at.isoformat(),
            "completions": [ts.isoformat() for ts in self.completions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Habit":
        """
        Reconstruct a Habit from a dictionary produced by :meth:`to_dict`.

        Args:
            data: Dictionary with keys name, description, periodicity,
                  created_at, and completions.

        Returns:
            A fully populated Habit instance.
        """
        habit = cls(
            name=data["name"],
            description=data["description"],
            periodicity=data["periodicity"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )
        for ts_str in data.get("completions", []):
            habit.completions.append(datetime.fromisoformat(ts_str))
        habit.completions.sort()
        return habit

    def __repr__(self) -> str:
        return (
            f"Habit(name={self.name!r}, periodicity={self.periodicity!r}, "
            f"completions={len(self.completions)})"
        )
