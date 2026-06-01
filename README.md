# Трекер успеха

Локальное веб-приложение в стиле dark/neon dashboard для личного учета привычек и целей.

<img width="420" height="320" alt="image" src="https://github.com/user-attachments/assets/c063cd5c-81d6-46cd-b472-77089e1e7465" /><img width="520" height="320" alt="image" src="https://github.com/user-attachments/assets/c7326ba7-1b69-440a-b3df-8d54fc860075" />


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
