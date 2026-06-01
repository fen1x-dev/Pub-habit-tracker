FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data
ENV PORT=8000
ENV APP_TZ_OFFSET_HOURS=3

WORKDIR /app

COPY app.py .
COPY templates ./templates
COPY static ./static
COPY public ./public

RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "app.py"]
