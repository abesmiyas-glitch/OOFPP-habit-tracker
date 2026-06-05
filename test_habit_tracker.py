"""
test_habit_tracker.py

Unit test suite for the Habit Tracker application.

Run with pytest::

    pytest test_habit_tracker.py -v

or with unittest::

    python -m unittest test_habit_tracker -v

Tests cover:
    - Habit creation and validation
    - Completion recording
    - Period key generation (daily and weekly)
    - Streak calculation (current and longest)
    - Analytics module (all public functions)
    - Storage (SQLite round-trip)
    - Seed data fixture
    - Edit habit (description, periodicity, completions cleared on period change)
"""

import unittest
import os
import tempfile
from datetime import datetime, timedelta

# Module imports (adjust sys.path so tests can run from any directory)
import sys
sys.path.insert(0, os.path.dirname(__file__))

from habit import Habit
from analytics import (
    get_all_habits,
    get_habits_by_periodicity,
    get_longest_streak_all,
    get_longest_streak_for_habit,
    get_struggle_habits,
    habit_summary,
)
from storage import initialise_db, save_habit, load_all_habits, delete_habit, habit_exists
from seed_data import seed_database


# ---------------------------------------------------------------------------
# Habit class tests
# ---------------------------------------------------------------------------

class TestHabitCreation(unittest.TestCase):
    """Tests for Habit.__init__."""

    def test_default_created_at(self):
        h = Habit("h1", "desc", "daily")
        self.assertIsNotNone(h.created_at)

    def test_custom_created_at(self):
        ts = datetime(2024, 1, 15, 9, 0)
        h = Habit("h1", "desc", "daily", created_at=ts)
        self.assertEqual(h.created_at, ts)

    def test_invalid_periodicity(self):
        with self.assertRaises(ValueError):
            Habit("h1", "desc", "monthly")

    def test_invalid_periodicity_hourly(self):
        """Any unrecognised periodicity string should raise ValueError."""
        with self.assertRaises(ValueError):
            Habit("h1", "desc", "hourly")

    def test_invalid_periodicity_empty_string(self):
        with self.assertRaises(ValueError):
            Habit("h1", "desc", "")

    def test_valid_periodicity_daily(self):
        h = Habit("h1", "desc", "daily")
        self.assertEqual(h.periodicity, "daily")

    def test_valid_periodicity_weekly(self):
        h = Habit("h1", "desc", "weekly")
        self.assertEqual(h.periodicity, "weekly")

    def test_initial_completions_empty(self):
        h = Habit("h1", "desc", "daily")
        self.assertEqual(h.completions, [])

    def test_name_stored(self):
        h = Habit("my_habit", "desc", "daily")
        self.assertEqual(h.name, "my_habit")

    def test_description_stored(self):
        h = Habit("h1", "my description", "daily")
        self.assertEqual(h.description, "my description")


class TestHabitCompletion(unittest.TestCase):
    """Tests for Habit.complete."""

    def setUp(self):
        self.habit = Habit("h", "desc", "daily")

    def test_complete_defaults_to_now(self):
        before = datetime.now()
        ts = self.habit.complete()
        after = datetime.now()
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after)

    def test_complete_custom_datetime(self):
        ts = datetime(2024, 3, 10, 8, 30)
        result = self.habit.complete(ts)
        self.assertEqual(result, ts)
        self.assertIn(ts, self.habit.completions)

    def test_completions_remain_sorted(self):
        self.habit.complete(datetime(2024, 3, 12))
        self.habit.complete(datetime(2024, 3, 10))
        self.habit.complete(datetime(2024, 3, 11))
        dates = [c.date() for c in self.habit.completions]
        self.assertEqual(dates, sorted(dates))

    def test_multiple_completions_same_day(self):
        """Multiple completions in the same day are stored but count as one period."""
        self.habit.complete(datetime(2024, 3, 10, 8, 0))
        self.habit.complete(datetime(2024, 3, 10, 20, 0))
        self.assertEqual(len(self.habit.completions), 2)
        self.assertEqual(len(self.habit.completed_periods()), 1)

    def test_completed_periods_returns_unique_periods(self):
        """completed_periods() must deduplicate — 3 completions on 2 days = 2 periods."""
        self.habit.complete(datetime(2024, 3, 10, 8, 0))
        self.habit.complete(datetime(2024, 3, 10, 18, 0))
        self.habit.complete(datetime(2024, 3, 11, 9, 0))
        periods = self.habit.completed_periods()
        self.assertEqual(len(periods), 2)

    def test_completed_periods_empty_when_no_completions(self):
        self.assertEqual(self.habit.completed_periods(), [])

    def test_completed_periods_weekly_same_week(self):
        """Two completions in the same ISO week count as one weekly period."""
        h = Habit("w", "d", "weekly")
        h.complete(datetime(2024, 3, 11, 9, 0))   # Monday
        h.complete(datetime(2024, 3, 14, 18, 0))  # Thursday, same week
        self.assertEqual(len(h.completed_periods()), 1)

    def test_completed_periods_weekly_different_weeks(self):
        h = Habit("w", "d", "weekly")
        h.complete(datetime(2024, 3, 11))  # week A
        h.complete(datetime(2024, 3, 18))  # week B
        self.assertEqual(len(h.completed_periods()), 2)

    def test_complete_returns_datetime(self):
        """complete() should always return a datetime object."""
        result = self.habit.complete(datetime(2024, 5, 1))
        self.assertIsInstance(result, datetime)


class TestPeriodKeys(unittest.TestCase):
    """Tests for period key generation."""

    def test_daily_period_key(self):
        h = Habit("h", "d", "daily")
        dt = datetime(2024, 3, 15, 10, 0)
        self.assertEqual(h._period_key(dt), (2024, 3, 15))

    def test_daily_period_key_midnight(self):
        h = Habit("h", "d", "daily")
        dt = datetime(2024, 3, 15, 0, 0, 0)
        self.assertEqual(h._period_key(dt), (2024, 3, 15))

    def test_daily_period_key_end_of_day(self):
        h = Habit("h", "d", "daily")
        dt = datetime(2024, 3, 15, 23, 59, 59)
        self.assertEqual(h._period_key(dt), (2024, 3, 15))

    def test_weekly_period_key_same_week(self):
        h = Habit("h", "d", "weekly")
        monday = datetime(2024, 3, 11, 9, 0)   # Monday week 11
        friday = datetime(2024, 3, 15, 17, 0)  # Friday same week
        self.assertEqual(h._period_key(monday), h._period_key(friday))

    def test_weekly_period_key_different_weeks(self):
        h = Habit("h", "d", "weekly")
        week_a = datetime(2024, 3, 11)
        week_b = datetime(2024, 3, 18)
        self.assertNotEqual(h._period_key(week_a), h._period_key(week_b))

    def test_weekly_period_key_year_boundary(self):
        """Last day of one year vs first day of next year must be different periods."""
        h = Habit("h", "d", "weekly")
        dec_31 = datetime(2023, 12, 31)
        jan_7 = datetime(2024, 1, 7)
        self.assertNotEqual(h._period_key(dec_31), h._period_key(jan_7))

    def test_daily_keys_are_tuples_of_length_3(self):
        h = Habit("h", "d", "daily")
        key = h._period_key(datetime(2024, 6, 1))
        self.assertIsInstance(key, tuple)
        self.assertEqual(len(key), 3)


class TestStreaks(unittest.TestCase):
    """Tests for streak calculation."""

    def _daily_habit_with_days(self, day_offsets, start=None):
        start = start or datetime(2024, 3, 1)
        h = Habit("h", "d", "daily", created_at=start)
        for offset in day_offsets:
            h.complete(start + timedelta(days=offset, hours=8))
        return h

    def _weekly_habit_with_weeks(self, week_offsets, start=None):
        start = start or datetime(2024, 1, 1)
        h = Habit("h", "d", "weekly", created_at=start)
        for offset in week_offsets:
            h.complete(start + timedelta(weeks=offset, days=2))
        return h

    def test_longest_streak_daily_no_gaps(self):
        h = self._daily_habit_with_days(range(7))
        self.assertEqual(h.longest_streak(), 7)

    def test_longest_streak_daily_with_gap(self):
        # days 0-4, then gap on day 5, then 6-9 → longest is 5
        h = self._daily_habit_with_days([0, 1, 2, 3, 4, 6, 7, 8, 9])
        self.assertEqual(h.longest_streak(), 5)

    def test_longest_streak_daily_two_equal_runs(self):
        """When two runs tie, longest_streak should return the tie value."""
        h = self._daily_habit_with_days([0, 1, 2, 4, 5, 6])
        self.assertEqual(h.longest_streak(), 3)

    def test_longest_streak_daily_single_day(self):
        h = self._daily_habit_with_days([0])
        self.assertEqual(h.longest_streak(), 1)

    def test_longest_streak_weekly_no_gap(self):
        h = self._weekly_habit_with_weeks(range(4))
        self.assertEqual(h.longest_streak(), 4)

    def test_longest_streak_weekly_with_gap(self):
        h = self._weekly_habit_with_weeks([0, 1, 3])
        self.assertEqual(h.longest_streak(), 2)

    def test_longest_streak_weekly_single_week(self):
        h = self._weekly_habit_with_weeks([0])
        self.assertEqual(h.longest_streak(), 1)

    def test_longest_streak_no_completions(self):
        h = Habit("h", "d", "daily")
        self.assertEqual(h.longest_streak(), 0)

    def test_current_streak_no_completions(self):
        h = Habit("h", "d", "daily")
        self.assertEqual(h.current_streak(), 0)

    def test_current_streak_includes_today(self):
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        h = Habit("h", "d", "daily", created_at=yesterday - timedelta(days=5))
        h.complete(yesterday)
        h.complete(today)
        self.assertGreaterEqual(h.current_streak(), 2)

    def test_current_streak_broken(self):
        """If the most recent completion is not in the current period, streak is 0."""
        past = datetime(2020, 1, 1, 8, 0)
        h = Habit("h", "d", "daily", created_at=past)
        h.complete(past)
        h.complete(past + timedelta(days=1))
        self.assertEqual(h.current_streak(), 0)

    def test_single_completion_streak_is_one(self):
        today = datetime.now()
        h = Habit("h", "d", "daily", created_at=today - timedelta(days=1))
        h.complete(today)
        self.assertEqual(h.current_streak(), 1)
        self.assertEqual(h.longest_streak(), 1)

    def test_current_streak_weekly_active(self):
        """current_streak on a weekly habit completed this week should be >= 1."""
        today = datetime.now()
        # Complete this week (day 0 of the current week) and last week
        days_since_monday = today.weekday()
        this_monday = today - timedelta(days=days_since_monday)
        last_monday = this_monday - timedelta(weeks=1)
        h = Habit("h", "d", "weekly", created_at=last_monday - timedelta(weeks=1))
        h.complete(last_monday + timedelta(days=2))
        h.complete(this_monday + timedelta(days=2))
        self.assertGreaterEqual(h.current_streak(), 2)

    def test_current_streak_weekly_broken(self):
        """Weekly habit not completed this week or last week → streak 0."""
        past = datetime(2020, 1, 6)  # A Monday in 2020
        h = Habit("h", "d", "weekly", created_at=past)
        h.complete(past)
        h.complete(past + timedelta(weeks=1))
        self.assertEqual(h.current_streak(), 0)

    def test_longest_streak_multiple_completions_per_period(self):
        """Duplicate completions within the same period must not inflate the streak."""
        start = datetime(2024, 4, 1)
        h = Habit("h", "d", "daily", created_at=start)
        for day in range(3):
            # Two completions each day
            h.complete(start + timedelta(days=day, hours=8))
            h.complete(start + timedelta(days=day, hours=20))
        self.assertEqual(h.longest_streak(), 3)


class TestSerialisation(unittest.TestCase):
    """Tests for Habit.to_dict and Habit.from_dict."""

    def test_round_trip_daily(self):
        h = Habit("sleep", "Sleep 8 hours", "daily", created_at=datetime(2024, 1, 1))
        h.complete(datetime(2024, 1, 2, 23, 0))
        h.complete(datetime(2024, 1, 3, 22, 30))
        restored = Habit.from_dict(h.to_dict())
        self.assertEqual(restored.name, h.name)
        self.assertEqual(restored.description, h.description)
        self.assertEqual(restored.periodicity, h.periodicity)
        self.assertEqual(restored.created_at, h.created_at)
        self.assertEqual(restored.completions, h.completions)

    def test_round_trip_weekly(self):
        """Serialisation round-trip must preserve a weekly habit correctly."""
        h = Habit("gym", "Go to gym", "weekly", created_at=datetime(2024, 1, 1))
        h.complete(datetime(2024, 1, 3, 10, 0))
        h.complete(datetime(2024, 1, 10, 10, 0))
        restored = Habit.from_dict(h.to_dict())
        self.assertEqual(restored.periodicity, "weekly")
        self.assertEqual(len(restored.completions), 2)

    def test_round_trip_no_completions(self):
        """A brand-new habit with no completions should survive serialisation."""
        h = Habit("fresh", "desc", "daily", created_at=datetime(2024, 6, 1))
        restored = Habit.from_dict(h.to_dict())
        self.assertEqual(restored.name, "fresh")
        self.assertEqual(restored.completions, [])

    def test_to_dict_contains_expected_keys(self):
        h = Habit("h", "d", "daily")
        d = h.to_dict()
        for key in ("name", "description", "periodicity", "created_at", "completions"):
            self.assertIn(key, d)

    def test_from_dict_returns_habit_instance(self):
        h = Habit("h", "d", "daily")
        restored = Habit.from_dict(h.to_dict())
        self.assertIsInstance(restored, Habit)


# ---------------------------------------------------------------------------
# Analytics module tests
# ---------------------------------------------------------------------------

class TestAnalytics(unittest.TestCase):
    """Tests for all public functions in analytics.py."""

    def setUp(self):
        base = datetime(2024, 1, 1, 8, 0)

        self.h_daily_good = Habit("good_daily", "desc", "daily", created_at=base)
        for i in range(10):
            self.h_daily_good.complete(base + timedelta(days=i, hours=1))

        self.h_daily_poor = Habit("poor_daily", "desc", "daily", created_at=base)
        for i in [0, 1, 5, 6]:
            self.h_daily_poor.complete(base + timedelta(days=i, hours=1))

        self.h_weekly = Habit("weekly_habit", "desc", "weekly", created_at=base)
        for w in range(3):
            self.h_weekly.complete(base + timedelta(weeks=w, days=2))

        self.habits = [self.h_daily_good, self.h_daily_poor, self.h_weekly]

    def test_get_all_habits(self):
        result = get_all_habits(self.habits)
        self.assertEqual(len(result), 3)

    def test_get_all_habits_empty(self):
        self.assertEqual(get_all_habits([]), [])

    def test_get_all_habits_returns_list(self):
        result = get_all_habits(self.habits)
        self.assertIsInstance(result, list)

    def test_get_habits_by_periodicity_daily(self):
        result = get_habits_by_periodicity(self.habits, "daily")
        self.assertTrue(all(h.periodicity == "daily" for h in result))
        self.assertEqual(len(result), 2)

    def test_get_habits_by_periodicity_weekly(self):
        result = get_habits_by_periodicity(self.habits, "weekly")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "weekly_habit")

    def test_get_habits_by_periodicity_empty(self):
        result = get_habits_by_periodicity(self.habits, "monthly")
        self.assertEqual(result, [])

    def test_get_habits_by_periodicity_on_empty_list(self):
        result = get_habits_by_periodicity([], "daily")
        self.assertEqual(result, [])

    def test_get_longest_streak_all(self):
        best, streak = get_longest_streak_all(self.habits)
        self.assertEqual(best.name, "good_daily")
        self.assertEqual(streak, 10)

    def test_get_longest_streak_all_empty(self):
        best, streak = get_longest_streak_all([])
        self.assertIsNone(best)
        self.assertEqual(streak, 0)

    def test_get_longest_streak_all_returns_habit_object(self):
        best, _ = get_longest_streak_all(self.habits)
        self.assertIsInstance(best, Habit)

    def test_get_longest_streak_all_single_habit(self):
        best, streak = get_longest_streak_all([self.h_daily_good])
        self.assertEqual(best.name, "good_daily")
        self.assertEqual(streak, 10)

    def test_get_longest_streak_for_habit(self):
        self.assertEqual(get_longest_streak_for_habit(self.h_daily_good), 10)
        self.assertEqual(get_longest_streak_for_habit(self.h_daily_poor), 2)

    def test_get_longest_streak_for_habit_no_completions(self):
        h = Habit("empty", "d", "daily")
        self.assertEqual(get_longest_streak_for_habit(h), 0)

    def test_get_longest_streak_for_habit_weekly(self):
        self.assertEqual(get_longest_streak_for_habit(self.h_weekly), 3)

    def test_get_struggle_habits_order(self):
        """Habits with more missed periods should appear first."""
        ranked = get_struggle_habits(self.habits, since=datetime(2024, 1, 11))
        names = [h.name for h, _ in ranked]
        self.assertEqual(names[0], "poor_daily")

    def test_get_struggle_habits_miss_counts_are_non_negative(self):
        ranked = get_struggle_habits(self.habits, since=datetime(2024, 1, 11))
        for _, misses in ranked:
            self.assertGreaterEqual(misses, 0)

    def test_get_struggle_habits_empty_list(self):
        result = get_struggle_habits([], since=datetime(2024, 1, 11))
        self.assertEqual(result, [])

    def test_get_struggle_habits_good_daily_zero_misses(self):
        """The habit completed every day should have 0 missed periods."""
        ranked = get_struggle_habits(self.habits, since=datetime(2024, 1, 11))
        miss_map = {h.name: misses for h, misses in ranked}
        self.assertEqual(miss_map["good_daily"], 0)

    def test_habit_summary_keys(self):
        summary = habit_summary(self.h_daily_good)
        for key in ("name", "description", "periodicity", "created_at",
                    "total_completions", "current_streak", "longest_streak",
                    "completion_history"):
            self.assertIn(key, summary)

    def test_habit_summary_completion_history(self):
        """completion_history must contain one datetime string per completion."""
        summary = habit_summary(self.h_daily_good)
        history = summary["completion_history"]
        self.assertEqual(len(history), len(self.h_daily_good.completions))
        import re
        pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        for ts_str in history:
            self.assertRegex(ts_str, pattern)

    def test_habit_summary_values(self):
        summary = habit_summary(self.h_daily_good)
        self.assertEqual(summary["name"], "good_daily")
        self.assertEqual(summary["total_completions"], 10)
        self.assertEqual(summary["longest_streak"], 10)

    def test_habit_summary_no_completions(self):
        h = Habit("blank", "d", "daily")
        summary = habit_summary(h)
        self.assertEqual(summary["total_completions"], 0)
        self.assertEqual(summary["current_streak"], 0)
        self.assertEqual(summary["longest_streak"], 0)
        self.assertEqual(summary["completion_history"], [])

    def test_habit_summary_weekly_habit(self):
        summary = habit_summary(self.h_weekly)
        self.assertEqual(summary["periodicity"], "weekly")
        self.assertEqual(summary["total_completions"], 3)


# ---------------------------------------------------------------------------
# Storage tests
# ---------------------------------------------------------------------------

class TestStorage(unittest.TestCase):
    """Tests for SQLite persistence (storage.py)."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        initialise_db(self.db_path)

    def tearDown(self):
        import gc, time
        gc.collect()
        for _ in range(5):
            try:
                os.unlink(self.db_path)
                break
            except PermissionError:
                time.sleep(0.1)

    def _make_habit(self, name="test", periodicity="daily"):
        h = Habit(name, "description", periodicity, created_at=datetime(2024, 1, 1))
        h.complete(datetime(2024, 1, 2, 9, 0))
        h.complete(datetime(2024, 1, 3, 9, 0))
        return h

    def test_save_and_load(self):
        h = self._make_habit()
        save_habit(h, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, h.name)
        self.assertEqual(len(loaded[0].completions), 2)

    def test_load_empty_db(self):
        result = load_all_habits(self.db_path)
        self.assertEqual(result, [])

    def test_save_updates_existing(self):
        h = self._make_habit()
        save_habit(h, self.db_path)
        h.complete(datetime(2024, 1, 4, 9, 0))
        save_habit(h, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded[0].completions), 3)

    def test_delete_habit(self):
        h = self._make_habit()
        save_habit(h, self.db_path)
        deleted = delete_habit(h.name, self.db_path)
        self.assertTrue(deleted)
        self.assertEqual(load_all_habits(self.db_path), [])

    def test_delete_nonexistent(self):
        result = delete_habit("ghost", self.db_path)
        self.assertFalse(result)

    def test_habit_exists_true(self):
        h = self._make_habit()
        save_habit(h, self.db_path)
        self.assertTrue(habit_exists(h.name, self.db_path))

    def test_habit_exists_false(self):
        self.assertFalse(habit_exists("ghost", self.db_path))

    def test_multiple_habits(self):
        for name in ["a", "b", "c"]:
            save_habit(self._make_habit(name), self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded), 3)

    def test_weekly_habit_round_trip(self):
        h = self._make_habit("w", "weekly")
        save_habit(h, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(loaded[0].periodicity, "weekly")

    def test_save_habit_with_no_completions(self):
        """A habit with zero completions should save and reload cleanly."""
        h = Habit("empty_habit", "no completions yet", "daily",
                  created_at=datetime(2024, 3, 1))
        save_habit(h, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].completions, [])

    def test_loaded_habits_are_habit_instances(self):
        save_habit(self._make_habit(), self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertIsInstance(loaded[0], Habit)

    def test_loaded_habit_preserves_description(self):
        h = Habit("h", "important description", "daily",
                  created_at=datetime(2024, 1, 1))
        save_habit(h, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(loaded[0].description, "important description")

    def test_loaded_habit_preserves_created_at(self):
        ts = datetime(2024, 1, 1, 0, 0, 0)
        h = Habit("h", "d", "daily", created_at=ts)
        save_habit(h, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(loaded[0].created_at, ts)

    def test_completions_order_preserved_after_load(self):
        """Completions should come back in chronological order after a DB round-trip."""
        h = self._make_habit()
        save_habit(h, self.db_path)
        loaded = load_all_habits(self.db_path)
        timestamps = loaded[0].completions
        self.assertEqual(timestamps, sorted(timestamps))

    def test_delete_removes_only_target(self):
        """Deleting one habit must leave other habits intact."""
        save_habit(self._make_habit("keep"), self.db_path)
        save_habit(self._make_habit("remove"), self.db_path)
        delete_habit("remove", self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "keep")


# ---------------------------------------------------------------------------
# Seed data tests
# ---------------------------------------------------------------------------

class TestSeedData(unittest.TestCase):
    """Tests for the seed / fixture data module."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        initialise_db(self.db_path)

    def tearDown(self):
        import gc, time
        gc.collect()
        for _ in range(5):
            try:
                os.unlink(self.db_path)
                break
            except PermissionError:
                time.sleep(0.1)

    def test_seed_inserts_five_habits(self):
        inserted = seed_database(self.db_path)
        self.assertEqual(len(inserted), 5)

    def test_seed_idempotent(self):
        seed_database(self.db_path)
        inserted_second = seed_database(self.db_path)
        self.assertEqual(inserted_second, [])

    def test_seed_habit_names(self):
        seed_database(self.db_path)
        habits = load_all_habits(self.db_path)
        names = {h.name for h in habits}
        expected = {
            "morning_meditation", "drink_water", "read", "exercise", "meal_prep"
        }
        self.assertEqual(names, expected)

    def test_seed_contains_weekly_habit(self):
        seed_database(self.db_path)
        habits = load_all_habits(self.db_path)
        weekly = [h for h in habits if h.periodicity == "weekly"]
        self.assertGreaterEqual(len(weekly), 1)

    def test_seed_contains_daily_habits(self):
        seed_database(self.db_path)
        habits = load_all_habits(self.db_path)
        daily = [h for h in habits if h.periodicity == "daily"]
        self.assertGreaterEqual(len(daily), 1)

    def test_seed_habits_have_completions(self):
        seed_database(self.db_path)
        habits = load_all_habits(self.db_path)
        for h in habits:
            self.assertGreater(len(h.completions), 0, f"{h.name} has no completions")

    def test_overwrite_flag(self):
        seed_database(self.db_path)
        inserted = seed_database(self.db_path, overwrite=True)
        self.assertEqual(len(inserted), 5)

    def test_seed_returns_list(self):
        result = seed_database(self.db_path)
        self.assertIsInstance(result, list)

    def test_seed_habits_span_at_least_four_weeks(self):
        """Each seeded habit should have completions spread across >= 4 weeks.
        A span of 21+ days (3 full week gaps) is the safe lower bound since a
        habit completed on day 0 and day 27 spans 4 calendar weeks but only
        27 timedelta days."""
        seed_database(self.db_path)
        habits = load_all_habits(self.db_path)
        for h in habits:
            if not h.completions:
                continue
            span = h.completions[-1] - h.completions[0]
            self.assertGreaterEqual(
                span.days, 21,
                f"{h.name} completions span only {span.days} days (expected >= 21)"
            )

    def test_seed_all_habits_are_habit_instances(self):
        seed_database(self.db_path)
        habits = load_all_habits(self.db_path)
        for h in habits:
            self.assertIsInstance(h, Habit)

    def test_seed_overwrite_replaces_completions(self):
        """After overwrite=True, total habits count should still be exactly 5."""
        seed_database(self.db_path)
        seed_database(self.db_path, overwrite=True)
        habits = load_all_habits(self.db_path)
        self.assertEqual(len(habits), 5)


# ---------------------------------------------------------------------------
# Edit habit tests
# ---------------------------------------------------------------------------

class TestEditHabit(unittest.TestCase):
    """Tests for the edit functionality added to cli.py and storage.py."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        initialise_db(self.db_path)
        self.habit = Habit("test_habit", "Original description", "daily",
                           created_at=datetime(2024, 1, 1))
        self.habit.complete(datetime(2024, 1, 2, 9, 0))
        self.habit.complete(datetime(2024, 1, 3, 9, 0))
        save_habit(self.habit, self.db_path)

    def tearDown(self):
        import gc, time
        gc.collect()
        for _ in range(5):
            try:
                os.unlink(self.db_path)
                break
            except PermissionError:
                time.sleep(0.1)

    def test_edit_description_persists(self):
        self.habit.description = "Updated description"
        save_habit(self.habit, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(loaded[0].description, "Updated description")

    def test_edit_description_keeps_completions(self):
        self.habit.description = "New description"
        save_habit(self.habit, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded[0].completions), 2)

    def test_edit_periodicity_persists(self):
        self.habit.periodicity = "weekly"
        self.habit.completions.clear()
        save_habit(self.habit, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(loaded[0].periodicity, "weekly")

    def test_edit_periodicity_clears_completions(self):
        self.habit.periodicity = "weekly"
        self.habit.completions.clear()
        save_habit(self.habit, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded[0].completions), 0)

    def test_edit_same_periodicity_keeps_completions(self):
        self.habit.description = "Changed description only"
        save_habit(self.habit, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded[0].completions), 2)

    def test_invalid_periodicity_not_accepted(self):
        with self.assertRaises(ValueError):
            Habit("h", "d", "monthly")

    def test_edit_both_fields(self):
        self.habit.description = "Completely new"
        self.habit.periodicity = "weekly"
        self.habit.completions.clear()
        save_habit(self.habit, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(loaded[0].description, "Completely new")
        self.assertEqual(loaded[0].periodicity, "weekly")
        self.assertEqual(len(loaded[0].completions), 0)

    def test_edit_description_to_empty_string(self):
        """An empty description string should be accepted and persisted."""
        self.habit.description = ""
        save_habit(self.habit, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(loaded[0].description, "")

    def test_edit_does_not_duplicate_habit(self):
        """Saving an edited habit must not create a duplicate row."""
        self.habit.description = "no dupes"
        save_habit(self.habit, self.db_path)
        loaded = load_all_habits(self.db_path)
        self.assertEqual(len(loaded), 1)


    def test_edit_periodicity_weekly_to_daily_clears_completions(self):
        """Round-trip: weekly → clear → daily should persist correctly."""
        h = Habit("wh", "d", "weekly", created_at=datetime(2024, 1, 1))
        h.complete(datetime(2024, 1, 3))
        save_habit(h, self.db_path)
        h.periodicity = "daily"
        h.completions.clear()
        save_habit(h, self.db_path)
        loaded = {hab.name: hab for hab in load_all_habits(self.db_path)}
        self.assertEqual(loaded["wh"].periodicity, "daily")
        self.assertEqual(len(loaded["wh"].completions), 0)


if __name__ == "__main__":
    unittest.main()
