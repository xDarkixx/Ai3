FROM nvidia/cuda:12.6.2-runtime-ubuntu24.04
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY training/requirements.txt /app/requirements.txt
RUN python3 -m pip install --break-system-packages --no-cache-dir -r /app/requirements.txt
COPY training_worker.py /app/training_worker.py
CMD ["python3","/app/training_worker.py"]
