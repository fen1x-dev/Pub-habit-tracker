# Трекер успеха

Локальное веб-приложение в стиле dark/neon dashboard для личного учета привычек и целей.

## Запуск

```bash
docker compose up -d --build
```

После запуска откройте:

```text
http://localhost:8000
```

Страницы приложения:

```text
http://localhost:8000        # привычки
http://localhost:8000/goals  # цели и заметки
```

## Остановка

```bash
docker compose down
```

## Локальный запуск без Docker

Python-зависимости не требуются.

```bash
python3 app.py
```

По умолчанию база будет создана в:

```text
./data/success_tracker.db
```
