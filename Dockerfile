FROM python:3.12-slim

COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1@sha256:46d6625e68cbbdd2efab4a20245977664513f13ffef47915b000d431adcea0b4 /lambda-adapter /opt/extensions/lambda-adapter

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=people_pulse.settings.production \
    AWS_LWA_PORT=8000 \
    AWS_LWA_READINESS_CHECK_PATH=/health/ \
    AWS_LWA_ASYNC_INIT=true

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY pyproject.toml README.md ./
COPY manage.py ./
COPY apps ./apps
COPY people_pulse ./people_pulse
COPY services ./services
COPY templates ./templates
COPY static ./static
COPY samples ./samples
COPY scripts ./scripts

RUN python -m pip install --no-cache-dir . \
    && DJANGO_SECRET_KEY=container-build-only \
       DJANGO_ALLOWED_HOSTS=localhost \
       DB_NAME=container_build \
       DB_USER=container_build \
       DB_PASSWORD=container-build-only \
       DB_HOST=localhost \
       python manage.py collectstatic --noinput \
    && chmod +x /app/scripts/start-cloud.sh \
    && chown -R app:app /app

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/', timeout=3)"

CMD ["/app/scripts/start-cloud.sh"]
