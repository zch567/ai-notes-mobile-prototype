FROM python:3.12-slim

WORKDIR /workspace

COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN pip install --no-cache-dir -r /workspace/backend/requirements.txt

COPY backend /workspace/backend

WORKDIR /workspace/backend
ENV BACKEND_HOST=0.0.0.0
ENV BACKEND_PORT=8000
ENV BACKEND_ALLOWED_INPUT_ROOT=/workspace
ENV BACKEND_OUTPUT_DIR=/workspace/backend/runtime

EXPOSE 8000
CMD ["python", "run.py"]
