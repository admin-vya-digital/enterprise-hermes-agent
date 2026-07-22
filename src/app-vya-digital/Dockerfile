# app-vya-digital — dashboard adaptado do cr:ux pessoal, lendo diretamente o
# volume de profiles compartilhado com vya-workforce-api/gateway, e falando
# com o vyadigital_api (hermes-interaction-api) só para o canal WhatsApp
# (connect/disconnect/QR). Ver ARCHITECTURE_NOTES.md nesta pasta.
#
# Sem venv do hermes-agent: este serviço não roda nenhum código do
# hermes-agent, só lê/escreve arquivos (state.db, produto.yaml,
# appointments.db etc.) dentro de profiles/<id>/.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./
COPY lib/ ./lib/
COPY index.html ./

COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

EXPOSE 9119

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "server.py"]
