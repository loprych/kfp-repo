FROM python:3.9-slim

WORKDIR /app

# Kopiowanie wymagań i instalacja zależności
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie pliku z kodem webhoka
COPY webhook_server.py .

# Zmienne środowiskowe z wartościami domyślnymi
ENV PORT=5000
ENV KUBEFLOW_ENDPOINT="http://ml-pipeline.kubeflow.svc.cluster.local:8888"
ENV KF_PIPELINES_SA_TOKEN_PATH="/var/run/secrets/kubeflow/pipelines/token"

# Ekspozycja portu dla aplikacji Flask
EXPOSE 5000

# Uruchomienie serwera
CMD ["python", "webhook_server.py"]