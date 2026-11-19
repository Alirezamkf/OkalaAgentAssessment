FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY agents/agent_service/requirements.txt .
RUN pip install \
    --no-cache-dir \
    --default-timeout=120 \
    --retries=5 \
    -r requirements.txt
COPY agents/agent_service/app ./app
COPY shared/okala_ai ./okala_ai
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
