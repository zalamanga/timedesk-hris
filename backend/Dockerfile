FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini entrypoint.sh ./
RUN groupadd --system hris && useradd --system --gid hris hris && chmod 755 entrypoint.sh

FROM base AS test
ENV PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest-cache"
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests ./tests
USER hris
CMD ["python", "-m", "pytest", "tests", "-q"]

FROM base AS runtime
USER hris
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
