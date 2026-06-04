"""
cli.py

Interactive command-line interface for the Habit Tracker.

Uses the `rich` library for terminal output tables, panels,
coloured text, and styled prompts.

Run directly:

    python cli.py

Or with sample habits pre-loaded::

    python cli.py --seed
"""

import os
import sys
from datetime import datetime
from typing import List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.rule import Rule
from rich import box

from habit import Habit
from storage import initialise_db, load_all_habits, save_habit, delete_habit
from analytics import (
    get_all_habits,
    get_habits_by_periodicity,
    get_longest_streak_all,
    get_longest_streak_for_habit,
    get_struggle_habits,
    habit_summary,
)


# Configuration


DB_PATH = os.environ.get("HABIT_DB_PATH", "habits.db")
console = Console()


# Display helpers


BANNER = """
[bold #fdc9c6] _   _       _     _ _   _____              _             [/]
[bold #fdc9c6]| | | |     | |   (_) | |_   _|            | |            [/]
[bold #fdc9c6]| |_| | __ _| |__  _| |_  | |_ __ __ _  ___| | _____ _ __ [/]
[bold #fdc9c6]|  _  |/ _` | '_ \\| | __| | | '__/ _` |/ __| |/ / _ \\ '__|[/]
[bold #fdc9c6]| | | | (_| | |_) | | |_ | | | | (_| | (__|   <  __/ |   [/]
[bold #fdc9c6]\\_| |_/\\__,_|_.__/|_|\\__\\_/_|  \\__,_|\\___|_|\\_\\___|_|   [/]
"""

MENU_ITEMS = [
    ("1",  "List all habits",               "[#B0E0E6]Get a list of all your tracked habits[/]"),
    ("2",  "Filter habits",  "[#B0E0E6]Get a list of only daily or weekly habits[/]"),
    ("3",  "Create a habit",                "[#B0E0E6]Create a new habit[/]"),
    ("4",  "Edit a habit",                  "[#B0E0E6]Update description or periodicity[/]"),
    ("5",  "Complete a habit",              "[#B0E0E6]Check off a habit[/]"),
    ("6",  "Delete a habit",                "[#B0E0E6]Permanently remove a habit[/]"),
    ("7",  "Longest streak among all habits",   "[#B0E0E6]Get the best streak across all habits[/]"),
    ("8",  "Longest streak of a habit", "[#B0E0E6]Get the best streak for one habit[/]"),
    ("9",  "Most struggled habits",         "[#B0E0E6]Habits you miss most often[/]"),
    ("10", "Habit details",        "[#B0E0E6]Get full profile and completion history of a habit[/]"),
    ("0",  "Quit",                          "[#AD1457]Exit the application[/]"),
]


def print_banner() -> None:
    console.print(BANNER)


def print_menu() -> None:
    table = Table(
        box=box.ROUNDED,
        border_style="#9a606c",
        header_style="bold white on #9a606c",
        title="[#48D1CC]HABIT TRACKER MENU[/]",
        title_style="#9a606c",
        padding=(0, 1),
    )
    table.add_column("Option",      style="bold #e68a8d", justify="center", width=8)
    table.add_column("Action",      style="bold white",  width=40)
    table.add_column("Description", width=50)

    for opt, action, desc in MENU_ITEMS:
        if opt == "0":
            table.add_row(f"[#AD1457]{opt}[/]", f"[#AD1457]{action}[/]", desc)
        else:
            table.add_row(opt, action, desc)

    console.print()
    console.print(table)
    console.print()


def section_header(title: str, color: str = "#FFF0F5") -> None:
    console.print()
    console.print(Rule(f"[bold {color}]{title}[/]", style=color))
    console.print()


def print_habit_table(habits: List[Habit], title: str = "Habits") -> None:
    if not habits:
        console.print(Panel("[#48D1CC]No habits found.[/]", border_style="#48D1CC"))
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="#DB7093",
        header_style="bold white on #DB7093",
        title=f"[bold #DB7093]{title}[/]",
        padding=(0, 1),
        show_lines=True,
    )
    table.add_column("ID",           style="bold #DB7093", justify="center", width=4)
    table.add_column("Name",        style="bold white",  width=26)
    table.add_column("Type",        style="#E0FFFF",        justify="center", width=8)
    table.add_column("Current Streak",      style="#E0FFFF",  justify="center", width=8)
    table.add_column("Completions", style="#FFE4E1",     justify="center", width=12)
    table.add_column("Created at",  style="#FFE4E1",   width=22)

    for i, h in enumerate(habits, 1):
        streak  = h.current_streak()
        period  = "[#FFDAB9]Daily[/]" if h.periodicity == "daily" else "[#FA8072]Weekly[/]"
        streak_disp = f"[bold #E0FFFF]{streak}[/]" if streak > 0 else "[dim]0[/]"
        created = h.created_at.strftime("%Y-%m-%d %H:%M:%S")
        table.add_row(str(i), h.name, period, streak_disp,
                      str(len(h.completions)), created)

    console.print(table)


def pick_habit(habits: List[Habit], prompt: str = "Select habit number"):
    print_habit_table(habits)
    try:
        raw = Prompt.ask(f"\n  [bold #FFE4C4]{prompt}[/]")
        idx = int(raw) - 1
        if 0 <= idx < len(habits):
            return habits[idx]
    except (ValueError, IndexError):
        pass
    console.print("[#DC143C]  Invalid selection.[/]")
    return None


def pause() -> None:
    console.print()
    Prompt.ask("[white]  Press Enter to continue[/]", default="")


# Menu actions


def action_list_habits(habits: List[Habit]) -> None:
    """Display all tracked habits."""
    section_header("All Habits")
    if not habits:
        console.print(Panel(
            "[#48D1CC]No habits tracked yet.\nUse option [bold]3[/] to create your first habit.[/]",
            border_style="#AFEEEE",
        ))
        return
    print_habit_table(habits, "All Your Habits")


def action_list_by_period(habits: List[Habit]) -> None:
    """Display habits filtered by periodicity."""
    section_header("Filter Habits by Periodicity")
    choice = Prompt.ask(
        " [bold #FFEFD5] Type either d / daily for daily habits or w / weekly for weekly habits, or press enter for daily",
        choices=["d", "w", "daily", "weekly"],
        default="d",
        show_default=False, 
    ).lower()
    period_map = {"d": "daily", "w": "weekly", "daily": "daily", "weekly": "weekly"}
    period   = period_map[choice]
    filtered = get_habits_by_periodicity(habits, period)
    if not filtered:
        console.print(f"[#48D1CC]  No {period} habits found.[/]")
        return
    print_habit_table(filtered, f"{period.capitalize()} Habits")


def action_create_habit(habits: List[Habit]) -> List[Habit]:
    """Create and persist a new habit."""
    section_header("Create a New Habit", "#FFF0F5")

    name = Prompt.ask("  [bold]Enter habit name[/] (unique)").strip()
    if not name:
        console.print("[#DC143C]  Name cannot be empty.[/]")
        return habits
    if any(h.name == name for h in habits):
        console.print(f"[#DC143C]  A habit named '[bold]{name}[/]' already exists.[/]")
        return habits

    description = Prompt.ask("  [bold]Enter habit description[/]").strip()
    if not description:
        console.print("[#DC143C]  Description cannot be empty.[/]")
        return habits

    period_raw = Prompt.ask(
        "  [bold]Choose periodicity (d for daily or w for weekly / Press Enter for daily)[/]",
        choices=["d", "w", "daily", "weekly"],
        default="d",
        show_default=False, 
    ).lower()
    period_map  = {"d": "daily", "w": "weekly", "daily": "daily", "weekly": "weekly"}
    periodicity = period_map[period_raw]

    habit = Habit(name=name, description=description, periodicity=periodicity)
    save_habit(habit, DB_PATH)
    habits.append(habit)

    console.print(Panel(
        f"[bold #9a606c]✓[/] Habit [bold #BC8F8F]'{name}'[/] created successfully!\n"
        f"  Periodicity : [#48D1CC]{periodicity}[/]\n"
        f"  Created at  : [dim]{habit.created_at.strftime('%Y-%m-%d %H:%M:%S')}[/]",
        border_style="#AFEEEE",
        title="[#AFEEEE]Habit Created[/]",
    ))
    return habits


def action_edit_habit(habits: List[Habit]) -> List[Habit]:
    """Edit the description and/or periodicity of an existing habit."""
    section_header("Edit a Habit", "#FFF0F5")
    if not habits:
        console.print("[#48D1CC]  No habits to edit.[/]")
        return habits

    habit = pick_habit(habits, "Select a habit to edit (Enter habit ID)")
    if habit is None:
        return habits

    console.print(f"\n  Current description : [#AFEEEE]{habit.description}[/]")
    new_desc = Prompt.ask(
        "  New description [dim](Enter to keep)[/]", default=""
    ).strip()

    console.print(f"  Current periodicity : [#AFEEEE]{habit.periodicity}[/]")
    per_choice = Prompt.ask(
        "  New periodicity [dim](d/w, Enter to keep)[/]",
        choices=["d", "w", "daily", "weekly", ""],
        default="",
    ).lower()
    period_map = {"d": "daily", "w": "weekly", "daily": "daily", "weekly": "weekly"}

    changed = False

    if new_desc:
        habit.description = new_desc
        changed = True

    if per_choice and per_choice in period_map:
        new_period = period_map[per_choice]
        if new_period != habit.periodicity:
            habit.periodicity = new_period
            habit.completions.clear()
            console.print(Panel(
                "[yellow]⚠  [#FFE4C4] Periodicity changed successfully — all previous completions have been cleared.[/]",
                border_style="#AFEEEE",
            ))
        changed = True
    elif per_choice and per_choice not in period_map:
        console.print("[#DC143C]  Invalid periodicity — unchanged.[/]")

    if changed:
        save_habit(habit, DB_PATH)
        console.print(f"\n[bold #9a606c]  ✓ Habit '[#BC8F8F]{habit.name}[/]' updated successfully.[/]")
    else:
        console.print(f"\n[dim]  No changes made to '[#BC8F8F]{habit.name}'.[/]")

    return habits


def action_delete_habit(habits: List[Habit]) -> List[Habit]:
    """Delete a habit and all its data."""
    section_header("Delete a Habit", "#FFF0F5")
    if not habits:
        console.print("[#48D1CC]  No habits to delete.[/]")
        return habits

    habit = pick_habit(habits, "Select a habit to delete (Enter habit ID)")
    if habit is None:
        return habits

    confirmed = Confirm.ask(
        f"\n  By confirming, the deletion can not be undone  [#AFEEEE] Do you confirm the deletion of '[bold]{habit.name}[/]' Type y to confirm or n to cancel? "
    )
    if not confirmed:
        console.print("[dim]  Deletion cancelled.[/]")
        return habits

    delete_habit(habit.name, DB_PATH)
    habits = [h for h in habits if h.name != habit.name]
    console.print(Panel(
        f"[bold #9a606c]✓[/] Habit [bold]'[#BC8F8F]{habit.name}'[/] has been permanently deleted.",
        border_style="#AFEEEE",
        title="[#48D1CC]Habit Deleted[/]",
    ))
    return habits


def action_complete_habit(habits: List[Habit]) -> List[Habit]:
    """Check off a habit task."""
    section_header("Complete a Habit", "#FFF0F5")
    if not habits:
        console.print("[#48D1CC]  No habits to complete.[/]")
        return habits

    habit = pick_habit(habits, "Select a habit to complete")
    if habit is None:
        return habits

    console.print("\n  [bold #FFF0F5]Press Enter to use the current time, or type a custom datetime.[/]")
    custom = Prompt.ask(
        "  [bold]Datetime[/] [dim](YYYY-MM-DD HH:MM or HH:MM:SS)[/]",
        default="",
    ).strip()

    if not custom:
        ts = habit.complete()
    else:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                ts = datetime.strptime(custom, fmt)
                habit.complete(ts)
                break
            except ValueError:
                continue
        else:
            console.print("[#DC143C]  Invalid datetime format.[/]")
            return habits

    save_habit(habit, DB_PATH)
    console.print(Panel(
        f"[bold #9a606c]✓[/] [bold #BC8F8F]{habit.name}[/] completed!\n"
        f"  Date & Time    : [bold]{ts.strftime('%Y-%m-%d  %H:%M:%S')}[/]\n"
        f"  Current streak : [bold #FFE4C4]{habit.current_streak()}[/] period(s)",
        border_style="#AFEEEE",
        title="[#B0E0E6]Task Completed[/]",
    ))
    return habits


def action_longest_streak_all(habits: List[Habit]) -> None:
    """Show the habit with the overall longest streak."""
    section_header("Longest Streak — All Habits", "#FFF0F5")
    best_habit, streak = get_longest_streak_all(habits)
    if best_habit is None:
        console.print("[#48D1CC]  No habits tracked.[/]")
        return
    console.print(Panel(
        f"[bold #9a606c]🏆  {best_habit.name}[/]\n\n"
        f"  Longest streak ever : [bold #AD1457]{streak}[/] period(s)\n"
        f"  Periodicity         : [#48D1CC]{best_habit.periodicity}[/]",
        border_style="#AFEEEE",
        title="[#B0E0E6]Best Streak[/]",
    ))


def action_longest_streak_habit(habits: List[Habit]) -> None:
    """Show the longest streak for a selected habit."""
    section_header("Longest Streak — Single Habit", "#FFF0F5")
    if not habits:
        console.print("[#48D1CC]  No habits tracked.[/]")
        return

    habit = pick_habit(habits, "Select a habit")
    if habit is None:
        return

    streak = get_longest_streak_for_habit(habit)
    console.print(Panel(
        f"[bold #9a606c]{habit.name}[/]\n\n"
        f"  Longest streak ever : [bold #BC8F8F]{streak}[/] period(s)\n"
        f"  Current streak      : [bold #48D1CC]{habit.current_streak()}[/] period(s)",
        border_style="#AFEEEE",
        title="[#B0E0E6]Streak Details[/]",
    ))



def action_struggle_habits(habits: List[Habit]) -> None:
    console.print("\n[bold #FFF0F5]Struggle Habits Ranking[/]")

    
    console.print(
        "\n  [bold #FFF0F5]Press Enter to use current time, or enter a cutoff date.[/]"
    )

    custom = Prompt.ask(
        "  [bold]Cutoff datetime[/] [dim](YYYY-MM-DD HH:MM or YYYY-MM-DD HH:MM:SS)[/]",
        default=""
    ).strip()

    
    if not custom:
        since = None  # will default to now inside the function
    else:
        since = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                since = datetime.strptime(custom, fmt)
                break
            except ValueError:
                continue

        if since is None:
            console.print("[#DC143C]  Invalid datetime format.[/]")
            return

    ranked = get_struggle_habits(habits, since=since)

    if not ranked:
        console.print("[dim]  No habits found.[/]")
        return

    
    console.print("\n  [bold]Most struggled habits:[/]")
    for i, (habit, count) in enumerate(ranked, 1):
        console.print(f"  {i}. {habit.name} — [#AD1457]{count} broken periods[/]")

def action_habit_detail(habits: List[Habit]) -> None:
    """Show a detailed summary and full completion history for a habit."""
    section_header("Habit Detail / Summary", "#FFF0F5")
    if not habits:
        console.print("[#48D1CC]  No habits tracked.[/]")
        return

    habit = pick_habit(habits, "Select a habit")
    if habit is None:
        return

    summary = habit_summary(habit)

    # Info panel
    info = (
        f"[bold #DB7093]{summary['name']}[/]\n\n"
        f"  [bold white]Description :[/]   [#33C7D8]{summary['description']}[/]\n"
        f"  [bold white]Periodicity :[/]   [#33C7D8]{summary['periodicity']}[/]\n"
        f"  [bold white]Created at  :[/]   [#33C7D8]{summary['created_at']}[/]\n\n"
        f"  [bold white]Completions :[/]   [#33C7D8]{summary['total_completions']}[/]\n"
        f"  [bold white]Cur. streak :[/]   [#33C7D8]{summary['current_streak']}[/] period(s)\n"
        f"  [bold white]Best streak :[/]   [#33C7D8]{summary['longest_streak']}[/] period(s)"
    )
    console.print(Panel(info, border_style="#0077B6", title="[#AFEEEE]Habit Summary[/]"))

    # Completion history table
    console.print()
    history = summary.get("completion_history", [])
    if not history:
        console.print(Panel(
            "[#48D1CC]No completions recorded yet.[/]",
            border_style="#90E0EF",
        ))
        return

    hist_table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="#ADD8E6",
        header_style="bold white on #0077B6",
        title="[bold #ADD8E6]Completion History — Date & Time of Each Completion[/]",
        padding=(0, 2),
        show_lines=True,
    )
    hist_table.add_column("#",       justify="center", width=6,  style="bold #33C7D8")
    hist_table.add_column("Date",    justify="center", width=14, style="bold white")
    hist_table.add_column("Time",    justify="center", width=12, style="#B0DADA")
    hist_table.add_column("Weekday", justify="center", width=12, style="dim white")

    for i, ts_str in enumerate(history, 1):
        dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        hist_table.add_row(
            str(i),
            dt.strftime("%Y-%m-%d"),
            dt.strftime("%H:%M:%S"),
            dt.strftime("%A"),
        )

    console.print(hist_table)



# Main loop


MODIFYING = {"3", "4", "5", "6"}

DISPATCH = {
    "1":  action_list_habits,
    "2":  action_list_by_period,
    "3":  action_create_habit,
    "4":  action_edit_habit,
    "5":  action_complete_habit,
    "6":  action_delete_habit,
    "7":  action_longest_streak_all,
    "8":  action_longest_streak_habit,
    "9":  action_struggle_habits,
    "10": action_habit_detail,
}


def run(seed: bool = False) -> None:
    """
    Initialise the database and start the interactive CLI.

    Args:
        seed: If True, pre-populate with 5 sample habits before the menu.
    """
    initialise_db(DB_PATH)

    if seed:
        from seed_data import seed_database
        inserted = seed_database(DB_PATH, overwrite=True)
        console.print(Panel(
            "[#BC8F8F]✓[/] Sample habits loaded: "
            + ", ".join(f"[#FFE4C4]{n}[/]" for n in inserted),
            border_style="#BC8F8F",
            title="[#BC8F8F]Sample Data[/]",
        ))

    habits: List[Habit] = load_all_habits(DB_PATH)

    print_banner()
    console.print("[#FFF0F5]                              Welcome to Habit Tracker![/]")
    console.print("[#F8F8FF]                      Please select a number from the menu below to get started.[/]\n")

    while True:
        print_menu()
        choice = Prompt.ask("[bold #FFE4C4]  Your choice[/]").strip()

        if choice == "0":
            console.print(Panel(
                "[italic #D8BFD8]                        We are what we repeatedly do. Excellence, then, is not an act, but a habit - Aristotle [/]\n[bold #33C7D8]                             Thank you for using Habit Tracker. keep building good habits! 💪[/]",
                border_style="#D8BFD8",
            ))
            break

        handler = DISPATCH.get(choice)
        if handler is None:
            console.print("[red]  Unknown option — please choose a number from the menu.[/]")
            continue

        if choice in MODIFYING:
            habits = handler(habits)
        else:
            handler(habits)

        pause()

if __name__ == "__main__":
    seed_flag = "--seed" in sys.argv
    run(seed=seed_flag)
