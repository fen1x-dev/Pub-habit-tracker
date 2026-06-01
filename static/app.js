const page = document.querySelector(".app-shell");
const viewYear = Number(page?.dataset.year);
const viewMonth = Number(page?.dataset.month);

async function postJSON(url, payload = {}) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok || !data.ok) {
        throw new Error(data.error || "Ошибка запроса");
    }
    return data;
}

function escapeHTML(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function percent(done, total) {
    if (!total) return 0;
    return Math.round((done / total) * 100);
}

function reloadPage() {
    window.location.reload();
}

function closeCustomSelects(except = null) {
    document.querySelectorAll("[data-custom-select].is-open").forEach((select) => {
        if (select !== except) {
            select.classList.remove("is-open");
            select.querySelector("[data-select-trigger]")?.setAttribute("aria-expanded", "false");
        }
    });
}

function setMetric(key, value) {
    const node = document.querySelector(`[data-stat="${key}"]`);
    if (node) node.textContent = `${value}%`;
}

function updateTopStreaks(items) {
    const list = document.querySelector("#topStreaks");
    if (!list) return;

    if (!items.length) {
        list.innerHTML = '<li class="empty-note">Добавьте первую привычку.</li>';
        return;
    }

    const maxStreak = Math.max(1, ...items.map((item) => item.streak));
    list.innerHTML = items.map((item) => `
        <li class="streak-item">
            <span class="streak-name">${escapeHTML(item.name)}</span>
            <span class="streak-bar"><span style="width: ${percent(item.streak, maxStreak)}%"></span></span>
            <span class="streak-count">×${item.streak}</span>
        </li>
    `).join("");
}

function updateDailyProgress(items) {
    for (const item of items) {
        const tableValue = document.querySelector(`[data-day-total-value="${item.day}"]`);
        if (tableValue) tableValue.textContent = `${item.percent}%`;
    }
}

function updateTodayDonut(stats) {
    const donut = document.querySelector("#todayDonut");
    const meta = document.querySelector('[data-stat-meta="today"]');
    if (donut) donut.style.setProperty("--value", stats.today_percent);
    setMetric("today", stats.today_percent);
    if (meta) meta.textContent = `${stats.today_done} из ${stats.today_total}`;
}

function dayLineChartInnerHTML(days) {
    const width = 340;
    const height = 190;
    const left = 24;
    const right = 18;
    const top = 20;
    const bottom = 36;
    const usableWidth = width - left - right;
    const usableHeight = height - top - bottom;

    const points = days.map((item, index) => {
        const x = left + (usableWidth * index / Math.max(1, days.length - 1));
        const y = top + usableHeight - (usableHeight * Math.max(0, Math.min(100, item.percent)) / 100);
        return { x, y, day: item.day };
    });

    const pointString = points.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
    const dots = points.map((point, index) => (
        `<circle class="day-line-dot ${days[index]?.is_today ? "is-today" : ""}" data-day-dot="${point.day}" cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="3.8"></circle>`
    )).join("");
    const labels = points
        .filter((point, index) => point.day === 1 || index % 3 === 0 || index === points.length - 1)
        .map((point) => (
            `<span style="left:${((point.x / width) * 100).toFixed(2)}%">${point.day}</span>`
        )).join("");

    return `
        <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Процент выполнения по дням месяца">
            <g class="chart-grid">
                <line x1="${left}" y1="${top}" x2="${left}" y2="${height - bottom}"></line>
                <line x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}"></line>
                <line x1="${left}" y1="${top + usableHeight * 0.25}" x2="${width - right}" y2="${top + usableHeight * 0.25}"></line>
                <line x1="${left}" y1="${top + usableHeight * 0.5}" x2="${width - right}" y2="${top + usableHeight * 0.5}"></line>
                <line x1="${left}" y1="${top + usableHeight * 0.75}" x2="${width - right}" y2="${top + usableHeight * 0.75}"></line>
            </g>
            <polyline class="day-line" points="${pointString}"></polyline>
            ${dots}
        </svg>
        <div class="day-line-labels">${labels}</div>
    `;
}

function updateDailyLineChart(days) {
    const chart = document.querySelector("#dailyLineChart");
    if (chart) chart.innerHTML = dayLineChartInnerHTML(days);
}

function updateHabitMonthPercent(row) {
    if (!row) return;
    const checkboxes = [...row.querySelectorAll("[data-completion-checkbox]")];
    const completed = checkboxes.filter((item) => item.checked).length;
    const node = row.querySelector("[data-habit-month-percent]");
    if (node) node.textContent = `${percent(completed, checkboxes.length)}%`;
}

function updateStats(stats) {
    setMetric("month", stats.month_percent);
    const monthTotal = document.querySelector("[data-month-total]");
    if (monthTotal) monthTotal.textContent = `${stats.month_percent}%`;
    updateTodayDonut(stats);
    updateTopStreaks(stats.top_streaks || []);
    updateDailyProgress(stats.daily_progress || []);
    updateDailyLineChart(stats.daily_progress || []);
}

document.querySelectorAll("[data-completion-checkbox]").forEach((checkbox) => {
    checkbox.addEventListener("change", async () => {
        const checked = checkbox.checked;
        const cell = checkbox.closest(".check-cell");
        const row = checkbox.closest("[data-habit-row]");
        checkbox.disabled = true;
        cell?.classList.add("is-saving");

        try {
            const data = await postJSON("/api/completions", {
                habit_id: Number(checkbox.dataset.habitId),
                date: checkbox.dataset.date,
                completed: checked,
                year: viewYear,
                month: viewMonth,
            });
            cell?.classList.toggle("is-complete", checked);
            updateHabitMonthPercent(row);
            updateStats(data.stats);
        } catch (error) {
            checkbox.checked = !checked;
            alert(error.message);
        } finally {
            checkbox.disabled = false;
            cell?.classList.remove("is-saving");
        }
    });
});

document.querySelector("#habitForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.querySelector("#habitName");
    const name = input.value.trim();
    if (!name) return;

    try {
        await postJSON("/api/habits", { name });
        reloadPage();
    } catch (error) {
        alert(error.message);
    }
});

document.addEventListener("click", async (event) => {
    const selectTrigger = event.target.closest("[data-select-trigger]");
    const selectOption = event.target.closest("[data-select-option]");
    const habitArchive = event.target.closest("[data-archive-habit]");
    const taskArchive = event.target.closest("[data-task-archive]");
    const taskDelete = event.target.closest("[data-task-delete]");
    const todayTaskArchive = event.target.closest("[data-today-task-archive]");
    const todayTaskDelete = event.target.closest("[data-today-task-delete]");

    if (selectTrigger) {
        const select = selectTrigger.closest("[data-custom-select]");
        const willOpen = !select.classList.contains("is-open");
        closeCustomSelects(select);
        select.classList.toggle("is-open", willOpen);
        selectTrigger.setAttribute("aria-expanded", String(willOpen));
        return;
    }

    if (selectOption) {
        const select = selectOption.closest("[data-custom-select]");
        const hidden = select.querySelector("input[type='hidden']");
        const label = select.querySelector("[data-select-label]");
        const value = selectOption.dataset.value;
        const text = selectOption.dataset.label;

        hidden.value = value;
        label.textContent = text;
        select.querySelectorAll("[data-select-option]").forEach((option) => {
            option.classList.toggle("is-selected", option === selectOption);
            option.textContent = option === selectOption ? `✓ ${option.dataset.label}` : option.dataset.label;
        });
        closeCustomSelects();
        return;
    }

    if (!event.target.closest("[data-custom-select]")) {
        closeCustomSelects();
    }

    try {
        if (habitArchive) {
            await postJSON(`/api/habits/${habitArchive.dataset.archiveHabit}/archive`);
            reloadPage();
        }

        if (taskArchive) {
            await postJSON(`/api/tasks/${taskArchive.dataset.taskArchive}/archive`);
            reloadPage();
        }

        if (taskDelete) {
            await postJSON(`/api/tasks/${taskDelete.dataset.taskDelete}/delete`);
            reloadPage();
        }

        if (todayTaskArchive) {
            await postJSON(`/api/today-tasks/${todayTaskArchive.dataset.todayTaskArchive}/archive`);
            reloadPage();
        }

        if (todayTaskDelete) {
            await postJSON(`/api/today-tasks/${todayTaskDelete.dataset.todayTaskDelete}/delete`);
            reloadPage();
        }
    } catch (error) {
        alert(error.message);
    }
});

document.querySelector("#taskForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.querySelector("#taskTitle");
    const category = document.querySelector("#taskCategory");
    const importance = document.querySelector("#taskImportance");
    const urgency = document.querySelector("#taskUrgency");
    const title = input.value.trim();
    if (!title) return;

    try {
        await postJSON("/api/tasks", {
            title,
            category: category?.value || "normal",
            importance: importance?.value || "medium",
            urgency: urgency?.value || "someday",
        });
        reloadPage();
    } catch (error) {
        alert(error.message);
    }
});

document.querySelector("#todayTaskForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = document.querySelector("#todayTaskTitle");
    const title = input.value.trim();
    if (!title) return;

    try {
        await postJSON("/api/today-tasks", { title });
        reloadPage();
    } catch (error) {
        alert(error.message);
    }
});

document.querySelectorAll("[data-task-complete]").forEach((checkbox) => {
    checkbox.addEventListener("change", async () => {
        checkbox.disabled = true;
        try {
            await postJSON(`/api/tasks/${checkbox.dataset.taskComplete}/complete`, {
                completed: checkbox.checked,
            });
            reloadPage();
        } catch (error) {
            checkbox.checked = !checkbox.checked;
            alert(error.message);
            checkbox.disabled = false;
        }
    });
});

document.querySelectorAll("[data-today-task-complete]").forEach((checkbox) => {
    checkbox.addEventListener("change", async () => {
        checkbox.disabled = true;
        try {
            await postJSON(`/api/today-tasks/${checkbox.dataset.todayTaskComplete}/complete`, {
                completed: checkbox.checked,
            });
            reloadPage();
        } catch (error) {
            checkbox.checked = !checkbox.checked;
            alert(error.message);
            checkbox.disabled = false;
        }
    });
});
