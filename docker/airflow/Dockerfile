FROM apache/airflow:2.8.1-python3.11

USER root

# Install Chrome + dependencies for Selenium
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev wget gnupg2 unzip \
    chromium chromium-driver \
    fonts-liberation libnss3 libxss1 libasound2 libatk-bridge2.0-0 \
    libgtk-3-0 libdrm2 libgbm1 && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /tmp/tbb_staging && chmod 777 /tmp/tbb_staging

ENV CHROME_BINARY_PATH=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver
ENV SELENIUM_HEADLESS=true

USER airflow

# Install deps but keep Airflow's own SQLAlchemy version
COPY source/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    pip install --no-cache-dir 'sqlalchemy>=1.4,<2.0'
