FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Playwright/Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    procps \
    libnss3 \
    libxss1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    libvulkan1 \
    libx11-xcb1 \
    fonts-liberation \
    libu2f-udev \
    xdg-utils \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (chromium only to save space, with deps just in case)
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 8000

# Set environment variables for scheduler default
ENV CRON_DAY=1
ENV CRON_HOUR=9
ENV CRON_MINUTE=0

# Run FastAPI app with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
