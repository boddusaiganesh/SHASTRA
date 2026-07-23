FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install cmdstan for Prophet forecasting
RUN python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"

# Copy application code
COPY . .

# Create uploads directory so evidence file saving never fails with FileNotFoundError
RUN mkdir -p /app/uploads

# Expose port
EXPOSE 8000

# Start the application:
# 1. Run DB migrations (|| true means: warn but don't crash if DB is unreachable at boot)
# 2. Start the FastAPI server on the PORT provided by Render (falls back to 8000)
CMD ["sh", "-c", "alembic upgrade head || echo 'WARNING: alembic migration failed, starting anyway' && python main.py"]
