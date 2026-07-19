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

# Expose port
EXPOSE 8000

# Start the application
CMD ["sh", "-c", "alembic upgrade head && python main.py"]
