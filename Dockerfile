FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY api_server.py ./api_server.py
COPY web ./web
COPY update_agent.py ./update_agent.py
COPY sitecustomize.py ./sitecustomize.py
ENV AI3_DB=/data/ai3.db
ENV AI3_ENABLE_ADVANCED_SECURITY=1
EXPOSE 8080 8090 8091
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8080"]
