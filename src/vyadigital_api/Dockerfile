# API de interação com o hermes-agent (proxy/wrapper para a vya-workforce-api
# em homologação) — serviço independente do stack docker_hermes.
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY __init__.py main.py docker_api/
COPY core/ docker_api/core/
COPY clients/ docker_api/clients/
COPY models/ docker_api/models/
COPY routers/ docker_api/routers/

COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "docker_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
