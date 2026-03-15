FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_HOST=0.0.0.0
ENV PYTHONPATH=/app/src
EXPOSE 5000

CMD ["python", "-m", "src.app"]
