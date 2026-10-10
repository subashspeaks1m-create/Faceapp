FROM python:3.12-slim
WORKDIR /app
COPY apps/api-server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY packages/shared-types /app/shared-types
COPY apps/api-server /app
ENV PYTHONPATH=/app/shared-types
RUN useradd --uid 10001 --create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
