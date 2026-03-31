FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV TZ=Asia/Seoul
RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

# Copy project files
COPY . .

# Setup cron
COPY scripts/crontab /etc/cron.d/portfolio-cron
RUN chmod 0644 /etc/cron.d/portfolio-cron && crontab /etc/cron.d/portfolio-cron

# Create data directory
RUN mkdir -p /app/data/raw

EXPOSE 8501 8001

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
