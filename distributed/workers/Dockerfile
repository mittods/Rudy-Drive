FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app/workers
WORKDIR /app

CMD ["python", "-m", "workers.upload_worker"]