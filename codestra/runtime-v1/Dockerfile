# syntax=docker.io/docker/dockerfile@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

ARG SUPERSET_BASE_IMAGE
FROM ${SUPERSET_BASE_IMAGE}

LABEL org.opencontainers.image.title="Codestra Superset"
LABEL org.opencontainers.image.description="Read-only Codestra business analytics with Keycloak and row-level-security boundaries"
LABEL org.opencontainers.image.vendor="Codestra"
LABEL codestra.artifact.model="repository-configured-signed-image"
LABEL codestra.upstream.executable-authority="apache-superset-6.1.0-official-image"

USER 0:0
RUN install -d -o 10001 -g 10001 -m 0555 /app/pythonpath /usr/share/codestra
COPY --chmod=0444 requirements-runtime.txt /tmp/requirements-runtime.txt
RUN uv pip install --python /app/.venv/bin/python --require-hashes --no-cache \
      --requirement /tmp/requirements-runtime.txt \
    && python -c 'import authlib, gevent, psycopg2; from gunicorn.workers.ggevent import GeventWorker' \
    && rm /tmp/requirements-runtime.txt
COPY --chown=10001:10001 --chmod=0444 codestra/runtime-v1/superset_config.py.example /app/pythonpath/superset_config.py
COPY --chown=10001:10001 --chmod=0444 codestra/runtime-v1/codestra_security_manager.py /app/pythonpath/codestra_security_manager.py
COPY --chown=10001:10001 --chmod=0555 codestra/runtime-v1/bootstrap_roles.py /app/pythonpath/bootstrap_roles.py
COPY --chown=10001:10001 --chmod=0555 codestra/runtime-v1/check_metadata_readiness.py /app/pythonpath/check_metadata_readiness.py
COPY --chown=10001:10001 --chmod=0444 codestra/runtime-v1/runtime.v1.json /usr/share/codestra/runtime.v1.json
COPY --chown=10001:10001 --chmod=0444 codestra/runtime-v1/analytics-control-plane.v1.json /usr/share/codestra/analytics-control-plane.v1.json
COPY --chown=10001:10001 --chmod=0444 codestra/release/image-build.v1.json /usr/share/codestra/image-build.v1.json
COPY --chown=10001:10001 --chmod=0444 codestra/release/runtime-base.lock.json /usr/share/codestra/runtime-base.lock.json

ENV SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
ENV PYTHONPATH=/app/pythonpath
USER 10001:10001
