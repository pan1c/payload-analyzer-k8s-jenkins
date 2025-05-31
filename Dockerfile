###############################################
# Stage 1 – base image with runtime deps only #
###############################################
FROM python:3.13-slim AS base

# Set working directory
WORKDIR /code

# Python output i.e. the stdout and stderr streams are sent straight to terminal
ENV PYTHONUNBUFFERED=1

# Install security updates and minimal system deps
# Update is questionable, it will increase security, but we will not have same image all the time
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Create non-root user (for security)
RUN adduser --disabled-password --no-create-home --gecos '' appuser

###############################################
# Stage 2 – test / dev image (extends base)   #
###############################################
FROM base AS dev

ENV PYTHONPATH=/code
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY app ./app
COPY tests ./tests

CMD ["pytest", "-q"]

###############################################
# Stage 3 – final production image            #
###############################################
FROM base AS prod

# Copy only the application code (no tests, no dev files)
COPY app ./app

# Switch to non-root user for security
USER appuser

EXPOSE 8081

# Use Gunicorn with UvicornWorker for production
# Gunicorn is a WSGI server that can serve ASGI apps via UvicornWorker
# Uvicorn is an ASGI server for running FastAPI applications
# Gunicron can handle signals and graceful shutdowns
# As this is microservice, we use a single worker
ENTRYPOINT ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8081", "--workers", "1", "--graceful-timeout", "60"]
