FROM python:3.12-slim
WORKDIR /srv
COPY apps/api-server/requirements.lock /srv/requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
# Keep the repository layout: the runtime resolves db/, model-registry.json and assets/ from it.
COPY packages/shared-types /srv/packages/shared-types
COPY apps/inference-engine /srv/apps/inference-engine
COPY apps/api-server /srv/apps/api-server
COPY db /srv/db
COPY model-registry.json /srv/model-registry.json
COPY assets/filters.json /srv/assets/filters.json
ENV PYTHONPATH=/srv/packages/shared-types:/srv/apps/api-server
WORKDIR /srv/apps/api-server
RUN useradd --uid 10001 --create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
