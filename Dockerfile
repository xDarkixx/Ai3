FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY api_server.py ./api_server.py
COPY web ./web
ENV AI3_DB=/data/ai3.db
EXPOSE 8080 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
