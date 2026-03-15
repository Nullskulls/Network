FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==22.0.0

COPY . .

ENV PYTHONPATH=/app/src
ENV PORT=53000

EXPOSE 53000

CMD ["sh", "-c", "gunicorn -w 2 -k gthread --threads 4 --timeout 120 --bind 0.0.0.0:${PORT} src.app:app"]
