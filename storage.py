"""
storage.py

Handles persistence of habit data using SQLite via the built-in sqlite3 module.

All habits and their completion timestamps are stored in a single SQLite
database file.  The schema uses two tables:

    habits       – one row per habit (name, description, periodicity, created_at)
    completions  – one row per check-off (habit_name FK, completed_at)

This module exposes four simple functions so that the rest of the application
never has to write SQL directly.
"""

import sqlite3
from datetime import datetime
from typing import List

from habit import Habit



# Schema helpers


_CREATE_HABITS = """
CREATE TABLE IF NOT EXISTS habits (
    name        TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    periodicity TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""

_CREATE_COMPLETIONS = """
CREATE TABLE IF NOT EXISTS completions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    habit_name   TEXT NOT NULL REFERENCES habits(name) ON DELETE CASCADE,
    completed_at TEXT NOT NULL
);
"""


def _get_connection(db_path: str) -> sqlite3.Connection:
    """
    Open OR create the SQLite database at *db_path* and return a connection
    with foreign-key enforcement enabled.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialise_db(db_path: str) -> None:
    """
    Create the database schema if it does not already exist.

    This is idempotent – This function is safe to run multiple times without changing the result.
    It is called on every application startup to ensure proper initialization.

    Args:
        db_path: File-system path to the SQLite database file.
    """
    with _get_connection(db_path) as conn:
        conn.execute(_CREATE_HABITS)
        conn.execute(_CREATE_COMPLETIONS)



# CRUD


def save_habit(habit: Habit, db_path: str) -> None:
    """
    Insert or replace a habit and all its completions in the database.
    The habit is inserted or updated (upsert) in the database.

    All stored completions for this habit are deleted and then
    reinserted from the current in-memory state.

    This ensures the database always matches the Habit object exactly
    and prevents duplicate completion entries after updates or re-saving.
    

    Args:
        habit:   The :class:`~habit.Habit` instance to persist.
        db_path: Path to the SQLite database.
    """
    with _get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO habits (name, description, periodicity, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description,
                periodicity  = excluded.periodicity,
                created_at   = excluded.created_at
            """,
            (
                habit.name,
                habit.description,
                habit.periodicity,
                habit.created_at.isoformat(),
            ),
        )
        # Replace completions wholesale
        conn.execute("DELETE FROM completions WHERE habit_name = ?", (habit.name,))
        conn.executemany(
            "INSERT INTO completions (habit_name, completed_at) VALUES (?, ?)",
            [(habit.name, ts.isoformat()) for ts in habit.completions],
        )


def load_all_habits(db_path: str) -> List[Habit]:
    """
    Load every habit with its completions from the database.
    
    This function retrieves habits from the 'habits' table, then loads
    all associated completion timestamps from the 'completions' table.
    
    Args:
        db_path: Path to the SQLite database.

    Returns:
        A list of :class:`~habit.Habit` instances, possibly empty.
    """
    with _get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT name, description, periodicity, created_at FROM habits ORDER BY created_at"
        ).fetchall()

        habits = []
        for name, description, periodicity, created_at in rows:
            habit = Habit(
                name=name,
                description=description,
                periodicity=periodicity,
                created_at=datetime.fromisoformat(created_at),
            )
            c_rows = conn.execute(
                "SELECT completed_at FROM completions WHERE habit_name = ? ORDER BY completed_at",
                (name,),
            ).fetchall()
            for (completed_at,) in c_rows:
                habit.completions.append(datetime.fromisoformat(completed_at))
            habits.append(habit)

    return habits


def delete_habit(name: str, db_path: str) -> bool:
    """
    Remove a habit and all its completion records from the database.

    Args:
        name:    The unique name of the habit to delete.
        db_path: Path to the SQLite database.

    Returns:
        True if a habit was deleted, False if no habit with that name existed.
    """
    with _get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM habits WHERE name = ?", (name,))
        return cursor.rowcount > 0


def habit_exists(name: str, db_path: str) -> bool:
    """
    Check whether a habit with the given name exists in the database.

    Args:
        name:    Habit name to look up.
        db_path: Path to the SQLite database.

    Returns:
        True if found, False otherwise.
    """
    with _get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM habits WHERE name = ?", (name,)
        ).fetchone()
        return row is not None
