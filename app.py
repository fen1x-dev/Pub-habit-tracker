import calendar
import json
import mimetypes
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("DATABASE_PATH", DATA_DIR / "success_tracker.db"))
PORT = int(os.environ.get("PORT", "8000"))
TZ_OFFSET_HOURS = int(os.environ.get("APP_TZ_OFFSET_HOURS", "3"))

PUBLIC_FILES = {
    "/favicon.ico",
    "/favicon-16x16.png",
    "/favicon-32x32.png",
    "/apple-touch-icon.png",
    "/android-chrome-192x192.png",
    "/android-chrome-512x512.png",
    "/site.webmanifest",
}

MONTHS = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

MONTHS_NAV = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

TASK_CATEGORIES = {
    "normal": "Обычное",
    "house": "Дом",
    "life": "Личное",
    "study": "Учёба",
    "work": "Работа",
}

TASK_IMPORTANCE = {
    "low": "Низкая",
    "medium": "Средняя",
    "high": "Высокая",
    "critical": "Критично",
}

TASK_URGENCY = {
    "urgent": "Срочно",
    "week": "Неделя",
    "month": "Месяц",
    "someday": "Позже",
}

TASK_CATEGORY_CHIP_CLASSES = {
    "normal": "chip-category-default",
    "house": "chip-category-home",
    "life": "chip-category-personal",
    "study": "chip-category-study",
    "work": "chip-category-work",
}

TASK_IMPORTANCE_CHIP_CLASSES = {
    "low": "chip-priority-low",
    "medium": "chip-priority-medium",
    "high": "chip-priority-high",
    "critical": "chip-priority-critical",
}

TASK_URGENCY_CHIP_CLASSES = {
    "urgent": "chip-time-urgent",
    "week": "chip-time-week",
    "month": "chip-time-month",
    "someday": "chip-time-later",
}

DAILY_PHRASES = [
    "Сегодня получится",
    "Держи темп",
    "Малый шаг важен",
    "Сделай один процент",
    "Спокойно и точно",
    "День для победы",
    "Фокус на главном",
    "Плюс один день",
    "Ты уже в пути",
    "Не сбавляй ход",
    "Собери серию",
    "Выбери действие",
    "Ритм сильнее рывка",
    "Делай без шума",
    "Сегодня твой ход",
    "Продолжай линию",
    "Накопи результат",
    "Доведи до галочки",
    "Будь верен плану",
    "Ещё один шаг",
]


def now_utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def local_today():
    tz = timezone(timedelta(hours=TZ_OFFSET_HOURS))
    return datetime.now(tz).date()


def parse_iso_date(value):
    return date.fromisoformat(str(value)[:10])


def safe_text(value):
    return escape(str(value), quote=True)


def category_label(value):
    return TASK_CATEGORIES.get(value or "normal", TASK_CATEGORIES["normal"])


def importance_label(value):
    return TASK_IMPORTANCE.get(value or "medium", TASK_IMPORTANCE["medium"])


def urgency_label(value):
    return TASK_URGENCY.get(value or "someday", TASK_URGENCY["someday"])


def chip_class(classes, value, fallback):
    return classes.get(value or "", fallback)


def daily_phrase():
    today = local_today()
    return DAILY_PHRASES[today.toordinal() % len(DAILY_PHRASES)]


def percent(done, total):
    if total <= 0:
        return 0
    return int(round((done / total) * 100))


def clamp_percent(value):
    return max(0, min(100, int(value)))


def add_month(year, month, delta):
    month_index = (year * 12 + (month - 1)) + delta
    return month_index // 12, month_index % 12 + 1


def month_label(year, month):
    return f"{MONTHS[month - 1]} {year}"


def month_url(year, month):
    return f"/?year={year}&month={month}"


def get_requested_month(query):
    today = local_today()
    try:
        year = int(query.get("year", [today.year])[0])
        month = int(query.get("month", [today.month])[0])
    except (TypeError, ValueError):
        return today.year, today.month

    if month < 1 or month > 12 or year < 1970 or year > 2100:
        return today.year, today.month

    return year, month


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                archived_at TEXT
            );

            CREATE TABLE IF NOT EXISTS habit_completions (
                habit_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (habit_id, date),
                FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS long_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'normal',
                importance TEXT NOT NULL DEFAULT 'medium',
                urgency TEXT NOT NULL DEFAULT 'someday',
                completed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                archived_at TEXT
            );

            CREATE TABLE IF NOT EXISTS today_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                task_date TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                archived_at TEXT
            );
            """
        )

        columns = {
            row["name"]
            for row in db.execute("PRAGMA table_info(long_tasks)").fetchall()
        }
        if "category" not in columns:
            db.execute(
                "ALTER TABLE long_tasks ADD COLUMN category TEXT NOT NULL DEFAULT 'normal'"
            )
        if "importance" not in columns:
            db.execute(
                "ALTER TABLE long_tasks ADD COLUMN importance TEXT NOT NULL DEFAULT 'medium'"
            )
        if "urgency" not in columns:
            db.execute(
                "ALTER TABLE long_tasks ADD COLUMN urgency TEXT NOT NULL DEFAULT 'someday'"
            )


def active_habits(db):
    return db.execute(
        """
        SELECT id, name, created_at
        FROM habits
        WHERE archived = 0
        ORDER BY id
        """
    ).fetchall()


def load_tasks(db):
    active = db.execute(
        """
        SELECT id, title, category, importance, urgency, completed
        FROM long_tasks
        WHERE archived = 0 AND completed = 0
        ORDER BY id DESC
        """
    ).fetchall()

    completed = db.execute(
        """
        SELECT id, title, category, importance, urgency, completed
        FROM long_tasks
        WHERE archived = 0 AND completed = 1
        ORDER BY completed_at DESC, id DESC
        """
    ).fetchall()

    return active, completed


def load_today_tasks(db):
    today = local_today().isoformat()
    active = db.execute(
        """
        SELECT id, title, completed
        FROM today_tasks
        WHERE archived = 0 AND completed = 0 AND task_date = ?
        ORDER BY id DESC
        """,
        (today,),
    ).fetchall()

    completed = db.execute(
        """
        SELECT id, title, completed
        FROM today_tasks
        WHERE archived = 0 AND completed = 1 AND task_date = ?
        ORDER BY completed_at DESC, id DESC
        """,
        (today,),
    ).fetchall()
    return active, completed


def completion_set_for_month(db, year, month):
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    rows = db.execute(
        """
        SELECT habit_id, date
        FROM habit_completions
        WHERE completed = 1 AND date BETWEEN ? AND ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    return {(row["habit_id"], row["date"]) for row in rows}


def grouped_completion_counts(db, habit_ids, start, end):
    if not habit_ids:
        return {}

    placeholders = ",".join("?" for _ in habit_ids)
    rows = db.execute(
        f"""
        SELECT date, COUNT(*) AS completed_count
        FROM habit_completions
        WHERE completed = 1
            AND date BETWEEN ? AND ?
            AND habit_id IN ({placeholders})
        GROUP BY date
        """,
        [start.isoformat(), end.isoformat(), *habit_ids],
    ).fetchall()
    return {row["date"]: row["completed_count"] for row in rows}


def top_habits(db, habits):
    if not habits:
        return []

    ids = [row["id"] for row in habits]
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"""
        SELECT habit_id, COUNT(*) AS completed_count, MIN(date) AS first_done, MAX(date) AS last_done
        FROM habit_completions
        WHERE completed = 1 AND habit_id IN ({placeholders})
        GROUP BY habit_id
        """,
        ids,
    ).fetchall()
    completed_by_habit = {row["habit_id"]: row for row in rows}
    today = local_today()
    result = []

    for habit in habits:
        completion_info = completed_by_habit.get(habit["id"])
        completed_count = completion_info["completed_count"] if completion_info else 0
        created = parse_iso_date(habit["created_at"])
        first_done = parse_iso_date(completion_info["first_done"]) if completion_info else created
        last_done = parse_iso_date(completion_info["last_done"]) if completion_info else today
        start = min(created, first_done)
        end = max(today, last_done)
        possible = max(1, (end - start).days + 1)
        value = clamp_percent(percent(completed_count, possible))
        result.append(
            {
                "id": habit["id"],
                "name": habit["name"],
                "percent": value,
                "completed": completed_count,
                "possible": possible,
            }
        )

    result.sort(key=lambda item: (-item["percent"], -item["completed"], item["name"].lower()))
    return result[:5]


def top_streaks(db, habits):
    if not habits:
        return []

    ids = [row["id"] for row in habits]
    placeholders = ",".join("?" for _ in ids)
    rows = db.execute(
        f"""
        SELECT habit_id, date
        FROM habit_completions
        WHERE completed = 1 AND habit_id IN ({placeholders})
        """,
        ids,
    ).fetchall()

    dates_by_habit = {habit["id"]: set() for habit in habits}
    for row in rows:
        dates_by_habit.setdefault(row["habit_id"], set()).add(row["date"])

    today = local_today()
    streaks = []
    for habit in habits:
        cursor = today
        streak = 0
        habit_dates = dates_by_habit.get(habit["id"], set())
        while cursor.isoformat() in habit_dates:
            streak += 1
            cursor -= timedelta(days=1)
        streaks.append(
            {
                "id": habit["id"],
                "name": habit["name"],
                "streak": streak,
            }
        )

    streaks.sort(key=lambda item: (-item["streak"], item["name"].lower()))
    return streaks[:5]


def weekly_progress(db, habit_ids, year, month):
    days_in_month = calendar.monthrange(year, month)[1]
    today = local_today()
    if year == today.year and month == today.month:
        anchor = today
    else:
        anchor = date(year, month, days_in_month)

    week_start = anchor - timedelta(days=anchor.weekday())
    first_week_start = week_start - timedelta(days=7 * 7)
    final_week_end = week_start + timedelta(days=6)
    counts = grouped_completion_counts(db, habit_ids, first_week_start, final_week_end)
    active_count = len(habit_ids)
    weeks = []

    for index in range(8):
        start = first_week_start + timedelta(days=index * 7)
        days = [start + timedelta(days=offset) for offset in range(7)]
        done = sum(counts.get(day.isoformat(), 0) for day in days)
        weeks.append(
            {
                "label": start.strftime("%d.%m"),
                "percent": percent(done, active_count * 7),
                "done": done,
                "total": active_count * 7,
            }
        )

    return weeks


def selected_week_range(year, month):
    today = local_today()
    days_in_month = calendar.monthrange(year, month)[1]
    anchor_day = min(today.day, days_in_month)
    anchor = date(year, month, anchor_day)
    start = anchor - timedelta(days=anchor.weekday())
    end = start + timedelta(days=6)
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)
    return max(start, month_start), min(end, month_end)


def calculate_stats(db, year, month, habits):
    habit_ids = [row["id"] for row in habits]
    active_count = len(habit_ids)
    today = local_today()
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = date(year, month, 1)
    month_end = date(year, month, days_in_month)
    month_counts = grouped_completion_counts(db, habit_ids, month_start, month_end)

    today_count = 0
    if habit_ids:
        placeholders = ",".join("?" for _ in habit_ids)
        today_count = db.execute(
            f"""
            SELECT COUNT(*) AS completed_count
            FROM habit_completions
            WHERE completed = 1
                AND date = ?
                AND habit_id IN ({placeholders})
            """,
            [today.isoformat(), *habit_ids],
        ).fetchone()["completed_count"]

    week_start, week_end = selected_week_range(year, month)
    week_dates = [
        week_start + timedelta(days=offset)
        for offset in range((week_end - week_start).days + 1)
    ]
    week_done = sum(month_counts.get(day.isoformat(), 0) for day in week_dates)

    month_done = sum(month_counts.values())
    daily_progress = []
    for day in range(1, days_in_month + 1):
        current = date(year, month, day)
        done = month_counts.get(current.isoformat(), 0)
        daily_progress.append(
            {
                "day": day,
                "date": current.isoformat(),
                "is_today": current == today,
                "percent": percent(done, active_count),
                "done": done,
                "total": active_count,
            }
        )

    return {
        "active_habits": active_count,
        "today_percent": percent(today_count, active_count),
        "today_done": today_count,
        "today_total": active_count,
        "week_percent": percent(week_done, active_count * len(week_dates)),
        "week_done": week_done,
        "week_total": active_count * len(week_dates),
        "week_label": f"{week_start.day}-{week_end.day} {MONTHS[month - 1].lower()}",
        "month_percent": percent(month_done, active_count * days_in_month),
        "month_done": month_done,
        "month_total": active_count * days_in_month,
        "daily_progress": daily_progress,
        "top_habits": top_habits(db, habits),
        "top_streaks": top_streaks(db, habits),
        "weekly_progress": weekly_progress(db, habit_ids, year, month),
    }


def stats_response(stats):
    return {
        "today_percent": stats["today_percent"],
        "today_done": stats["today_done"],
        "today_total": stats["today_total"],
        "week_percent": stats["week_percent"],
        "week_done": stats["week_done"],
        "week_total": stats["week_total"],
        "week_label": stats["week_label"],
        "month_percent": stats["month_percent"],
        "month_done": stats["month_done"],
        "month_total": stats["month_total"],
        "active_habits": stats["active_habits"],
        "daily_progress": stats["daily_progress"],
        "top_habits": stats["top_habits"],
        "top_streaks": stats["top_streaks"],
        "weekly_progress": stats["weekly_progress"],
    }


def render_streak_list(items):
    if not items:
        return '<li class="empty-note">Добавьте первую привычку.</li>'

    max_streak = max([item["streak"] for item in items] + [1])
    rows = []
    for item in items:
        width = percent(item["streak"], max_streak)
        rows.append(
            f"""
            <li class="streak-item">
                <span class="streak-name">{safe_text(item["name"])}</span>
                <span class="streak-bar"><span style="width: {width}%"></span></span>
                <span class="streak-count">×{item["streak"]}</span>
            </li>
            """
        )
    return "\n".join(rows)


def render_daily_progress(progress):
    if not progress:
        return '<p class="empty-note">Нет дней для отображения.</p>'

    today = local_today().isoformat()
    html = []
    for item in progress:
        current = parse_iso_date(item["date"])
        classes = ["chart-bar"]
        if current.weekday() >= 5:
            classes.append("is-weekend")
        if item["date"] == today:
            classes.append("is-today")
        label = item["day"] if item["day"] == 1 or (item["day"] - 1) % 3 == 0 else ""
        html.append(
            f"""
            <div class="{' '.join(classes)}" title="{item["day"]}: {item["percent"]}%">
                <span class="bar-fill" data-day="{item["day"]}" style="height: {item["percent"]}%"></span>
                <span class="bar-label">{label}</span>
                <span class="bar-value" data-day-value="{item["day"]}">{item["percent"]}%</span>
            </div>
            """
        )
    return "\n".join(html)


def render_today_donut(stats):
    value = clamp_percent(stats["today_percent"])
    return f"""
    <div class="today-donut" id="todayDonut" style="--value: {value}">
        <div class="donut-core">
            <strong data-stat="today">{value}%</strong>
            <span data-stat-meta="today">{stats["today_done"]} из {stats["today_total"]}</span>
        </div>
    </div>
    """


def render_day_line_chart(progress):
    if not progress:
        return '<p class="empty-note">Нет дней для отображения.</p>'

    points = []
    dots = []
    labels = []
    width = 340
    height = 190
    left = 24
    right = 18
    top = 20
    bottom = 36
    usable_width = width - left - right
    usable_height = height - top - bottom

    for index, item in enumerate(progress):
        x = left + (usable_width * index / max(1, len(progress) - 1))
        y = top + usable_height - (usable_height * clamp_percent(item["percent"]) / 100)
        points.append(f"{x:.1f},{y:.1f}")
        classes = "day-line-dot"
        if item["date"] == local_today().isoformat():
            classes += " is-today"
        dots.append(
            f'<circle class="{classes}" data-day-dot="{item["day"]}" cx="{x:.1f}" cy="{y:.1f}" r="3.8"></circle>'
        )
        if item["day"] == 1 or (item["day"] - 1) % 3 == 0 or item["day"] == len(progress):
            labels.append(
                f'<span style="left:{(x / width) * 100:.2f}%">{item["day"]}</span>'
            )

    return f"""
    <div class="day-line-chart" id="dailyLineChart">
        <svg viewBox="0 0 {width} {height}" role="img" aria-label="Процент выполнения по дням месяца">
            <g class="chart-grid">
                <line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}"></line>
                <line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}"></line>
                <line x1="{left}" y1="{top + usable_height * 0.25}" x2="{width - right}" y2="{top + usable_height * 0.25}"></line>
                <line x1="{left}" y1="{top + usable_height * 0.5}" x2="{width - right}" y2="{top + usable_height * 0.5}"></line>
                <line x1="{left}" y1="{top + usable_height * 0.75}" x2="{width - right}" y2="{top + usable_height * 0.75}"></line>
            </g>
            <polyline class="day-line" points="{' '.join(points)}"></polyline>
            {"".join(dots)}
        </svg>
        <div class="day-line-labels">{"".join(labels)}</div>
    </div>
    """


def render_week_chart(weeks):
    if not weeks:
        return '<p class="empty-note">Нет недель для отображения.</p>'

    points = []
    dots = []
    labels = []
    width = 320
    height = 160
    left = 22
    right = 16
    top = 18
    bottom = 32
    usable_width = width - left - right
    usable_height = height - top - bottom

    for index, item in enumerate(weeks):
        x = left + (usable_width * index / max(1, len(weeks) - 1))
        y = top + usable_height - (usable_height * clamp_percent(item["percent"]) / 100)
        points.append(f"{x:.1f},{y:.1f}")
        dots.append(
            f'<circle class="week-dot" data-week-dot="{index}" cx="{x:.1f}" cy="{y:.1f}" r="4"></circle>'
        )
        labels.append(
            f'<span style="left:{(x / width) * 100:.2f}%">{safe_text(item["label"])}</span>'
        )

    return f"""
    <div class="week-chart" id="weekChart">
        <svg viewBox="0 0 {width} {height}" role="img" aria-label="Процент выполнения по неделям">
            <g class="chart-grid">
                <line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}"></line>
                <line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}"></line>
                <line x1="{left}" y1="{top + usable_height * 0.25}" x2="{width - right}" y2="{top + usable_height * 0.25}"></line>
                <line x1="{left}" y1="{top + usable_height * 0.5}" x2="{width - right}" y2="{top + usable_height * 0.5}"></line>
                <line x1="{left}" y1="{top + usable_height * 0.75}" x2="{width - right}" y2="{top + usable_height * 0.75}"></line>
            </g>
            <polyline class="week-line" points="{' '.join(points)}"></polyline>
            {"".join(dots)}
        </svg>
        <div class="week-labels">{"".join(labels)}</div>
    </div>
    """


def render_dashboard(stats, year, month):
    streaks = render_streak_list(stats["top_streaks"])
    today_donut = render_today_donut(stats)
    days_line = render_day_line_chart(stats["daily_progress"])
    return f"""
    <section class="dashboard">
        <article class="chart-card streak-card">
            <h2>Серия дней · топ-5</h2>
            <ol class="streak-list" id="topStreaks">{streaks}</ol>
        </article>
        <article class="chart-card today-card">
            <h2>Успех за сегодня</h2>
            {today_donut}
        </article>
        <article class="chart-card">
            <h2>% по дням · {safe_text(MONTHS[month - 1])} {year}</h2>
            {days_line}
        </article>
    </section>
    """


def render_month_header(year, month):
    days_in_month = calendar.monthrange(year, month)[1]
    today = local_today()
    cells = []
    for day in range(1, days_in_month + 1):
        current = date(year, month, day)
        classes = ["day-head"]
        if current.weekday() >= 5:
            classes.append("is-weekend")
        if current == today:
            classes.append("is-today")
        cells.append(
            f"""
            <th class="{' '.join(classes)}">
                <span class="day-number">{day}</span>
                <span class="day-weekday">{WEEKDAYS[current.weekday()]}</span>
            </th>
            """
        )
    return "\n".join(cells)


def render_day_totals(progress, month_percent):
    cells = []
    for item in progress:
        classes = ["day-total-cell"]
        current = parse_iso_date(item["date"])
        if current.weekday() >= 5:
            classes.append("is-weekend")
        if current == local_today():
            classes.append("is-today")
        cells.append(
            f"""
            <td class="{' '.join(classes)}">
                <span data-day-total-value="{item["day"]}">{item["percent"]}%</span>
            </td>
            """
        )

    return f"""
    <tr class="daily-total-row">
        <th class="total-label">итого за день</th>
        {"".join(cells)}
        <td class="month-percent total-month" data-month-total>{month_percent}%</td>
    </tr>
    """


def render_habit_rows(habits, completions, year, month, stats):
    days_in_month = calendar.monthrange(year, month)[1]
    today = local_today()

    if not habits:
        return f"""
        <tr>
            <td class="empty-table" colspan="{days_in_month + 2}">Добавьте привычку, и здесь появится строка месяца.</td>
        </tr>
        """

    rows = []
    for habit in habits:
        cells = []
        completed_in_month = 0
        for day in range(1, days_in_month + 1):
            current = date(year, month, day)
            iso = current.isoformat()
            checked = (habit["id"], iso) in completions
            if checked:
                completed_in_month += 1
            classes = ["check-cell"]
            if current.weekday() >= 5:
                classes.append("is-weekend")
            if current == today:
                classes.append("is-today")
            if checked:
                classes.append("is-complete")
            cells.append(
                f"""
                <td class="{' '.join(classes)}">
                    <label class="check-wrap">
                        <input
                            type="checkbox"
                            data-completion-checkbox
                            data-habit-id="{habit["id"]}"
                            data-date="{iso}"
                            {"checked" if checked else ""}
                            aria-label="{safe_text(habit["name"])} {day} {safe_text(MONTHS[month - 1])}"
                        >
                        <span></span>
                    </label>
                </td>
                """
            )

        rows.append(
            f"""
            <tr data-habit-row="{habit["id"]}">
                <th class="habit-name-cell">
                    <span class="habit-name-content">
                        <span class="habit-dot" aria-hidden="true"></span>
                        <span class="habit-title">{safe_text(habit["name"])}</span>
                        <button class="icon-action" type="button" data-archive-habit="{habit["id"]}" title="Архивировать">×</button>
                    </span>
                </th>
                {"".join(cells)}
                <td class="month-percent" data-habit-month-percent>{percent(completed_in_month, days_in_month)}%</td>
            </tr>
            """
        )
    rows.append(render_day_totals(stats["daily_progress"], stats["month_percent"]))
    return "\n".join(rows)


def render_choice_dropdown(field_id, name, options, selected):
    selected_label = options[selected]
    buttons = []
    for value, label in options.items():
        selected_class = " is-selected" if value == selected else ""
        check = "✓ " if value == selected else ""
        buttons.append(
            f"""
            <button type="button" class="select-option{selected_class}" data-select-option data-value="{safe_text(value)}" data-label="{safe_text(label)}">
                {check}{safe_text(label)}
            </button>
            """
        )

    return f"""
    <div class="custom-select" data-custom-select>
        <input type="hidden" id="{safe_text(field_id)}" name="{safe_text(name)}" value="{safe_text(selected)}">
        <button type="button" class="select-trigger" data-select-trigger aria-expanded="false">
            <span data-select-label>{safe_text(selected_label)}</span>
            <span class="select-caret" aria-hidden="true"></span>
        </button>
        <div class="select-menu" data-select-menu>
            {"".join(buttons)}
        </div>
    </div>
    """


def render_goal_controls():
    return "\n".join(
        [
            render_choice_dropdown("taskCategory", "category", TASK_CATEGORIES, "normal"),
            render_choice_dropdown("taskImportance", "importance", TASK_IMPORTANCE, "medium"),
            render_choice_dropdown("taskUrgency", "urgency", TASK_URGENCY, "someday"),
        ]
    )


def render_today_task_list(tasks, completed=False):
    if not tasks:
        return '<li class="empty-note">Пока пусто.</li>'

    rows = []
    for task in tasks:
        checked = "checked" if completed else ""
        classes = "today-task-item is-done" if completed else "today-task-item"
        rows.append(
            f"""
            <li class="{classes}">
                <label class="today-task-check">
                    <input type="checkbox" data-today-task-complete="{task["id"]}" {checked}>
                    <span class="custom-radio"></span>
                    <span>{safe_text(task["title"])}</span>
                </label>
                <div class="today-task-actions">
                    <button type="button" class="icon-action" data-today-task-archive="{task["id"]}" title="Архивировать">×</button>
                    <button type="button" class="icon-action" data-today-task-delete="{task["id"]}" title="Удалить">−</button>
                </div>
            </li>
            """
        )
    return "\n".join(rows)


def render_today_tasks_card(active, completed):
    return f"""
    <section class="today-tasks-card">
        <div class="today-tasks-heading">
            <div>
                <h2>Задачи на сегодня</h2>
                <p>{safe_text(local_today().strftime("%d.%m.%Y"))}</p>
            </div>
            <div class="today-task-count">{len(completed)} / {len(active) + len(completed)}</div>
        </div>
        <form class="today-task-form" id="todayTaskForm">
            <input id="todayTaskTitle" name="title" type="text" maxlength="140" placeholder="+ Задача на сегодня..." autocomplete="off">
            <button type="submit">Добавить</button>
        </form>
        <div class="today-task-columns">
            <section>
                <h3>Активные</h3>
                <ul class="today-task-list">{render_today_task_list(active, completed=False)}</ul>
            </section>
            <section>
                <h3>Готово</h3>
                <ul class="today-task-list">{render_today_task_list(completed, completed=True)}</ul>
            </section>
        </div>
    </section>
    """


def render_goal_list(tasks, completed=False):
    if not tasks:
        return '<li class="empty-note">Пока пусто.</li>'

    rows = []
    for task in tasks:
        checked = "checked" if completed else ""
        classes = "goal-item is-done" if completed else "goal-item"
        category_class = chip_class(
            TASK_CATEGORY_CHIP_CLASSES,
            task["category"],
            TASK_CATEGORY_CHIP_CLASSES["normal"],
        )
        importance_class = chip_class(
            TASK_IMPORTANCE_CHIP_CLASSES,
            task["importance"],
            TASK_IMPORTANCE_CHIP_CLASSES["medium"],
        )
        urgency_class = chip_class(
            TASK_URGENCY_CHIP_CLASSES,
            task["urgency"],
            TASK_URGENCY_CHIP_CLASSES["someday"],
        )
        rows.append(
            f"""
            <li class="{classes}">
                <label class="goal-check">
                    <input type="checkbox" data-task-complete="{task["id"]}" {checked}>
                    <span class="custom-radio"></span>
                    <span class="goal-content">
                        <span class="goal-title">{safe_text(task["title"])}</span>
                        <span class="goal-meta">
                            <span class="goal-chip {category_class}">{safe_text(category_label(task["category"]))}</span>
                            <span class="goal-chip {importance_class}">{safe_text(importance_label(task["importance"]))}</span>
                            <span class="goal-chip {urgency_class}">{safe_text(urgency_label(task["urgency"]))}</span>
                        </span>
                    </span>
                </label>
                <div class="goal-actions">
                    <button type="button" class="icon-action" data-task-archive="{task["id"]}" title="Архивировать">×</button>
                    <button type="button" class="icon-action" data-task-delete="{task["id"]}" title="Удалить">−</button>
                </div>
            </li>
            """
        )
    return "\n".join(rows)


def render_goal_groups(tasks):
    if not tasks:
        return """
        <section class="goal-group">
            <h2>Обычное</h2>
            <ul class="goal-list"><li class="empty-note">Добавьте цель или заметку.</li></ul>
        </section>
        """

    html = []
    grouped = {}
    for task in tasks:
        grouped.setdefault(task["category"] or "normal", []).append(task)

    for category, label in TASK_CATEGORIES.items():
        group = grouped.get(category, [])
        if not group:
            continue
        html.append(
            f"""
            <section class="goal-group">
                <h2>{safe_text(label)}</h2>
                <ul class="goal-list">{render_goal_list(group, completed=False)}</ul>
            </section>
            """
        )
    return "\n".join(html)


def render_page(year, month):
    with get_db() as db:
        habits = active_habits(db)
        completions = completion_set_for_month(db, year, month)
        today_tasks_active, today_tasks_completed = load_today_tasks(db)
        stats = calculate_stats(db, year, month, habits)

    days_in_month = calendar.monthrange(year, month)[1]
    table_width = 300 + days_in_month * 30 + 58
    table_mobile_width = 155 + days_in_month * 42 + 54
    prev_year, prev_month = add_month(year, month, -1)
    next_year, next_month = add_month(year, month, 1)
    template = Template((BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8"))

    return template.substitute(
        year=year,
        month=month,
        title="Трекер успеха · привычки",
        daily_phrase=daily_phrase(),
        month_label=month_label(year, month),
        prev_url=month_url(prev_year, prev_month),
        next_url=month_url(next_year, next_month),
        prev_label=month_label(prev_year, prev_month),
        next_label=month_label(next_year, next_month),
        dashboard=render_dashboard(stats, year, month),
        day_headers=render_month_header(year, month),
        habit_table_width=table_width,
        habit_table_mobile_width=table_mobile_width,
        habit_rows=render_habit_rows(habits, completions, year, month, stats),
        month_percent=stats["month_percent"],
        today_tasks=render_today_tasks_card(today_tasks_active, today_tasks_completed),
    )


def render_goals_page():
    with get_db() as db:
        tasks_active, tasks_completed = load_tasks(db)

    total = len(tasks_active) + len(tasks_completed)
    template = Template((BASE_DIR / "templates" / "goals.html").read_text(encoding="utf-8"))
    return template.substitute(
        title="Трекер успеха · цели",
        daily_phrase=daily_phrase(),
        goal_controls=render_goal_controls(),
        total_goals=total,
        completed_goals=len(tasks_completed),
        remaining_goals=len(tasks_active),
        active_goal_groups=render_goal_groups(tasks_active),
        completed_goals_list=render_goal_list(tasks_completed, completed=True),
    )


def json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def validated_date(value):
    parsed = date.fromisoformat(str(value))
    if parsed.year < 1970 or parsed.year > 2100:
        raise ValueError("date out of range")
    return parsed


def current_stats_payload(db, payload):
    today = local_today()
    try:
        year = int(payload.get("year", today.year))
        month = int(payload.get("month", today.month))
        if month < 1 or month > 12:
            year, month = today.year, today.month
    except (TypeError, ValueError):
        year, month = today.year, today.month

    habits = active_habits(db)
    return stats_response(calculate_stats(db, year, month, habits))


class TrackerHandler(BaseHTTPRequestHandler):
    def send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_bytes(status, body, "application/json; charset=utf-8")

    def send_error_json(self, status, message):
        self.send_json(status, {"ok": False, "error": message})

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html", "/habits"}:
            year, month = get_requested_month(parse_qs(parsed.query))
            html = render_page(year, month).encode("utf-8")
            self.send_bytes(200, html, "text/html; charset=utf-8")
            return

        if parsed.path == "/goals":
            html = render_goals_page().encode("utf-8")
            self.send_bytes(200, html, "text/html; charset=utf-8")
            return

        if parsed.path == "/health":
            self.send_json(200, {"ok": True})
            return

        if parsed.path.startswith("/static/"):
            self.serve_static(parsed.path)
            return

        if parsed.path in PUBLIC_FILES:
            self.serve_public(parsed.path)
            return

        self.send_error_json(404, "Не найдено")

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            payload = json_body(self)
            if parsed.path == "/api/habits":
                self.create_habit(payload)
                return

            if parsed.path.startswith("/api/habits/") and parsed.path.endswith("/archive"):
                habit_id = int(parsed.path.split("/")[3])
                self.archive_habit(habit_id)
                return

            if parsed.path == "/api/completions":
                self.toggle_completion(payload)
                return

            if parsed.path == "/api/tasks":
                self.create_task(payload)
                return

            if parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/complete"):
                task_id = int(parsed.path.split("/")[3])
                self.complete_task(task_id, payload)
                return

            if parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/archive"):
                task_id = int(parsed.path.split("/")[3])
                self.archive_task(task_id)
                return

            if parsed.path.startswith("/api/tasks/") and parsed.path.endswith("/delete"):
                task_id = int(parsed.path.split("/")[3])
                self.delete_task(task_id)
                return

            if parsed.path == "/api/today-tasks":
                self.create_today_task(payload)
                return

            if parsed.path.startswith("/api/today-tasks/") and parsed.path.endswith("/complete"):
                task_id = int(parsed.path.split("/")[3])
                self.complete_today_task(task_id, payload)
                return

            if parsed.path.startswith("/api/today-tasks/") and parsed.path.endswith("/archive"):
                task_id = int(parsed.path.split("/")[3])
                self.archive_today_task(task_id)
                return

            if parsed.path.startswith("/api/today-tasks/") and parsed.path.endswith("/delete"):
                task_id = int(parsed.path.split("/")[3])
                self.delete_today_task(task_id)
                return

            self.send_error_json(404, "Не найдено")
        except (ValueError, json.JSONDecodeError):
            self.send_error_json(400, "Некорректные данные")
        except sqlite3.Error:
            self.send_error_json(500, "Ошибка базы данных")

    def serve_static(self, request_path):
        relative = request_path.replace("/static/", "", 1)
        target = (BASE_DIR / "static" / relative).resolve()
        static_root = (BASE_DIR / "static").resolve()
        if static_root not in target.parents or not target.is_file():
            self.send_error_json(404, "Не найдено")
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_bytes(200, target.read_bytes(), content_type)

    def serve_public(self, request_path):
        target = (PUBLIC_DIR / request_path.lstrip("/")).resolve()
        public_root = PUBLIC_DIR.resolve()
        if public_root not in target.parents or not target.is_file():
            self.send_error_json(404, "Не найдено")
            return

        if target.name == "site.webmanifest":
            content_type = "application/manifest+json"
        else:
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_bytes(200, target.read_bytes(), content_type)

    def create_habit(self, payload):
        name = str(payload.get("name", "")).strip()
        if not name:
            self.send_error_json(400, "Название обязательно")
            return
        if len(name) > 80:
            self.send_error_json(400, "Название слишком длинное")
            return

        with get_db() as db:
            cursor = db.execute(
                "INSERT INTO habits (name, created_at) VALUES (?, ?)",
                (name, now_utc_iso()),
            )
            db.commit()
            self.send_json(201, {"ok": True, "id": cursor.lastrowid, "name": name})

    def archive_habit(self, habit_id):
        with get_db() as db:
            db.execute(
                "UPDATE habits SET archived = 1, archived_at = ? WHERE id = ?",
                (now_utc_iso(), habit_id),
            )
            db.commit()
            self.send_json(200, {"ok": True})

    def toggle_completion(self, payload):
        habit_id = int(payload.get("habit_id"))
        completion_date = validated_date(payload.get("date"))
        completed = bool(payload.get("completed"))

        with get_db() as db:
            habit = db.execute(
                "SELECT id FROM habits WHERE id = ? AND archived = 0",
                (habit_id,),
            ).fetchone()
            if not habit:
                self.send_error_json(404, "Привычка не найдена")
                return

            if completed:
                db.execute(
                    """
                    INSERT INTO habit_completions (habit_id, date, completed, updated_at)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(habit_id, date)
                    DO UPDATE SET completed = 1, updated_at = excluded.updated_at
                    """,
                    (habit_id, completion_date.isoformat(), now_utc_iso()),
                )
            else:
                db.execute(
                    "DELETE FROM habit_completions WHERE habit_id = ? AND date = ?",
                    (habit_id, completion_date.isoformat()),
                )

            db.commit()
            self.send_json(200, {"ok": True, "stats": current_stats_payload(db, payload)})

    def create_task(self, payload):
        title = str(payload.get("title", "")).strip()
        category = str(payload.get("category", "normal")).strip()
        importance = str(payload.get("importance", "medium")).strip()
        urgency = str(payload.get("urgency", "someday")).strip()
        if category not in TASK_CATEGORIES:
            category = "normal"
        if importance not in TASK_IMPORTANCE:
            importance = "medium"
        if urgency not in TASK_URGENCY:
            urgency = "someday"
        if not title:
            self.send_error_json(400, "Название обязательно")
            return
        if len(title) > 160:
            self.send_error_json(400, "Название слишком длинное")
            return

        with get_db() as db:
            cursor = db.execute(
                """
                INSERT INTO long_tasks (title, category, importance, urgency, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, category, importance, urgency, now_utc_iso()),
            )
            db.commit()
            self.send_json(
                201,
                {
                    "ok": True,
                    "id": cursor.lastrowid,
                    "title": title,
                    "category": category,
                    "importance": importance,
                    "urgency": urgency,
                },
            )

    def complete_task(self, task_id, payload):
        completed = bool(payload.get("completed"))
        completed_at = now_utc_iso() if completed else None
        with get_db() as db:
            db.execute(
                "UPDATE long_tasks SET completed = ?, completed_at = ? WHERE id = ?",
                (1 if completed else 0, completed_at, task_id),
            )
            db.commit()
            self.send_json(200, {"ok": True})

    def archive_task(self, task_id):
        with get_db() as db:
            db.execute(
                "UPDATE long_tasks SET archived = 1, archived_at = ? WHERE id = ?",
                (now_utc_iso(), task_id),
            )
            db.commit()
            self.send_json(200, {"ok": True})

    def delete_task(self, task_id):
        with get_db() as db:
            db.execute("DELETE FROM long_tasks WHERE id = ?", (task_id,))
            db.commit()
            self.send_json(200, {"ok": True})

    def create_today_task(self, payload):
        title = str(payload.get("title", "")).strip()
        if not title:
            self.send_error_json(400, "Название обязательно")
            return
        if len(title) > 140:
            self.send_error_json(400, "Название слишком длинное")
            return

        with get_db() as db:
            cursor = db.execute(
                """
                INSERT INTO today_tasks (title, task_date, created_at)
                VALUES (?, ?, ?)
                """,
                (title, local_today().isoformat(), now_utc_iso()),
            )
            db.commit()
            self.send_json(201, {"ok": True, "id": cursor.lastrowid, "title": title})

    def complete_today_task(self, task_id, payload):
        completed = bool(payload.get("completed"))
        completed_at = now_utc_iso() if completed else None
        with get_db() as db:
            db.execute(
                """
                UPDATE today_tasks
                SET completed = ?, completed_at = ?
                WHERE id = ? AND task_date = ?
                """,
                (1 if completed else 0, completed_at, task_id, local_today().isoformat()),
            )
            db.commit()
            self.send_json(200, {"ok": True})

    def archive_today_task(self, task_id):
        with get_db() as db:
            db.execute(
                """
                UPDATE today_tasks
                SET archived = 1, archived_at = ?
                WHERE id = ? AND task_date = ?
                """,
                (now_utc_iso(), task_id, local_today().isoformat()),
            )
            db.commit()
            self.send_json(200, {"ok": True})

    def delete_today_task(self, task_id):
        with get_db() as db:
            db.execute(
                "DELETE FROM today_tasks WHERE id = ? AND task_date = ?",
                (task_id, local_today().isoformat()),
            )
            db.commit()
            self.send_json(200, {"ok": True})

    def log_message(self, format, *args):
        return


def main():
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), TrackerHandler)
    print(f"Трекер успеха запущен: http://localhost:{PORT}")
    print(f"Данные: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
