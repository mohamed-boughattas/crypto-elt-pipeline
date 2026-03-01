# 🚀 Deployment Guide

Production deployment strategies for the Crypto ELT Pipeline.

---

## 🎯 Overview

This guide covers deploying the Crypto ELT Pipeline from local development to production environments. The pipeline is designed to scale from a single developer machine to enterprise-grade deployments.

---

## 📋 Deployment Environments

### 1. Local Development (Current)

- **Purpose**: Development and testing
- **Components**: All services run locally
- **Database**: DuckDB (single file)
- **Orchestration**: Dagster dev server
- **API**: FastAPI with uvicorn
- **Dashboard**: Streamlit local server

### 2. Staging Environment

- **Purpose**: Integration testing and validation
- **Components**: Containerized services
- **Database**: PostgreSQL or cloud database
- **Orchestration**: Dagster with persistent storage
- **API**: FastAPI with production server
- **Dashboard**: Streamlit with authentication

### 3. Production Environment

- **Purpose**: Live data processing and serving
- **Components**: Orchestration platform (Kubernetes, ECS)
- **Database**: Enterprise database with backups
- **Orchestration**: Dagster with high availability
- **API**: FastAPI with load balancing
- **Dashboard**: Streamlit with enterprise features

---

## 🐳 Docker Deployment

### Prerequisites

- Docker and Docker Compose installed
- Docker Hub account (for pushing images)
- Basic Docker knowledge

### 1. Create Dockerfile

```dockerfile
# Dockerfile
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY pyproject.toml poetry.lock ./

# Install uv (package manager)
RUN pip install uv

# Install dependencies
RUN uv sync

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p data

# Expose ports
EXPOSE 8000 8501 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uv", "run", "streamlit", "run", "streamlit_dashboard/dashboard.py"]
```

### 2. Create docker-compose.yml

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Database service
  database:
    image: duckdb/duckdb:latest
    volumes:
      - ./data:/data
    ports:
      - "5432:5432"
    environment:
      - DUCKDB_PATH=/data/crypto.duckdb
    command: ["duckdb", "--server", "--port", "5432", "/data/crypto.duckdb"]

  # API service
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - DATABASE_URL=postgresql://user:password@database:5432/crypto
      - DAGSTER_HOME=/app/.dagster_home
    depends_on:
      - database
    command: ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

  # Dashboard service
  dashboard:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    environment:
      - DATABASE_URL=postgresql://user:password@database:5432/crypto
      - USE_API=true
    depends_on:
      - api
    command: ["uv", "run", "streamlit", "run", "streamlit_dashboard/dashboard.py", "--server.port", "8501"]

  # Dagster orchestration
  dagster:
    build: .
    ports:
      - "3000:3000"
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - .dagster_home:/app/.dagster_home
    environment:
      - DATABASE_URL=postgresql://user:password@database:5432/crypto
      - DAGSTER_HOME=/app/.dagster_home
    depends_on:
      - database
    command: ["uv", "run", "dagit", "-h", "0.0.0.0", "-p", "3000"]

  # Pipeline worker
  worker:
    build: .
    volumes:
      - ./data:/app/data
      - ./config:/app/config
      - .dagster_home:/app/.dagster_home
    environment:
      - DATABASE_URL=postgresql://user:password@database:5432/crypto
      - DAGSTER_HOME=/app/.dagster_home
    depends_on:
      - database
      - dagster
    command: ["uv", "run", "dagster", "run", "launch", "--daemon"]
```

### 3. Build and Run

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Clean up
docker-compose down -v --rmi all
```

### 4. Docker Compose Commands

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d api

# View logs for specific service
docker-compose logs -f api

# Scale services
docker-compose up -d --scale worker=3

# Run pipeline manually
docker-compose exec worker uv run python -c "from src.crypto_elt_pipeline.defs import crypto_pipeline; crypto_pipeline.run()"

# Access database
docker-compose exec database duckdb /data/crypto.duckdb

# Health check
curl http://localhost:8000/health
```

---

## ☁️ Cloud Deployment

### AWS Deployment

#### Option 1: ECS (Elastic Container Service)

```yaml
# ecs-task-definition.json
{
  "family": "crypto-elt-pipeline",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "api",
      "image": "your-account/crypto-elt-api:latest",
      "portMappings": [{"containerPort": 8000}],
      "environment": [
        {"name": "DATABASE_URL", "value": "postgresql://..."},
        {"name": "ENVIRONMENT", "value": "production"}
      ]
    },
    {
      "name": "dashboard",
      "image": "your-account/crypto-elt-dashboard:latest",
      "portMappings": [{"containerPort": 8501}],
      "environment": [
        {"name": "DATABASE_URL", "value": "postgresql://..."},
        {"name": "USE_API", "value": "true"}
      ]
    }
  ]
}
```

#### Option 2: EKS (Elastic Kubernetes Service)

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crypto-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: crypto-api
  template:
    metadata:
      labels:
        app: crypto-api
    spec:
      containers:
      - name: api
        image: your-account/crypto-elt-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: crypto-secrets
              key: database-url
---
apiVersion: v1
kind: Service
metadata:
  name: crypto-api-service
spec:
  selector:
    app: crypto-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Google Cloud Platform (GCP)

#### Cloud Run Deployment

```yaml
# cloudbuild.yaml
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', 'gcr.io/$PROJECT_ID/crypto-api:$COMMIT_SHA', '.']
- name: 'gcr.io/cloud-builders/docker'
  args: ['push', 'gcr.io/$PROJECT_ID/crypto-api:$COMMIT_SHA']
- name: 'gcr.io/cloud-builders/gcloud'
  args: ['run', 'deploy', 'crypto-api', '--image', 'gcr.io/$PROJECT_ID/crypto-api:$COMMIT_SHA', '--region', 'us-central1', '--platform', 'managed', '--allow-unauthenticated']
```

#### Deployment Commands

```bash
# Build and deploy API
gcloud builds submit --config cloudbuild.yaml

# Deploy to Cloud Run
gcloud run deploy crypto-api \
  --image gcr.io/PROJECT_ID/crypto-api \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated

# Deploy dashboard
gcloud run deploy crypto-dashboard \
  --image gcr.io/PROJECT_ID/crypto-dashboard \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated
```

### Azure Deployment

#### Azure Container Instances

```bash
# Create resource group
az group create --name crypto-elt-rg --location eastus

# Create container instance
az container create \
  --resource-group crypto-elt-rg \
  --name crypto-api \
  --image your-registry/crypto-api:latest \
  --cpu 2 \
  --memory 4 \
  --ports 8000 \
  --environment-variables DATABASE_URL="postgresql://..."

# View logs
az container logs --resource-group crypto-elt-rg --name crypto-api
```

---

## 🗄️ Database Migration

### From DuckDB to PostgreSQL

#### 1. Schema Migration

```sql
-- Create PostgreSQL schema
CREATE TABLE raw.crypto_prices (
    coin VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    market_cap DECIMAL(20,2) NOT NULL,
    volume DECIMAL(20,2) NOT NULL,
    PRIMARY KEY (coin, recorded_at)
);

CREATE TABLE staging.stg_crypto_prices (
    coin VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    market_cap DECIMAL(20,2) NOT NULL,
    volume DECIMAL(20,2) NOT NULL,
    PRIMARY KEY (coin, recorded_at)
);

CREATE TABLE mart.fct_crypto_candlesticks (
    coin VARCHAR(50) NOT NULL,
    trade_date DATE NOT NULL,
    open_price DECIMAL(18,8) NOT NULL,
    high_price DECIMAL(18,8) NOT NULL,
    low_price DECIMAL(18,8) NOT NULL,
    close_price DECIMAL(18,8) NOT NULL,
    daily_volume DECIMAL(20,2) NOT NULL,
    volatility_pct DECIMAL(10,4) NOT NULL,
    samples_count INTEGER NOT NULL,
    sma_7 DECIMAL(18,8),
    sma_25 DECIMAL(18,8),
    bb_middle DECIMAL(18,8),
    bb_upper DECIMAL(18,8),
    bb_lower DECIMAL(18,8),
    bb_width DECIMAL(10,4),
    bb_position DECIMAL(10,4),
    daily_change_pct DECIMAL(10,4),
    price_range DECIMAL(18,8),
    PRIMARY KEY (coin, trade_date)
);
```

#### 2. Data Migration

```python
# migrate_data.py
import duckdb
import psycopg2
import pandas as pd

def migrate_data():
    # Connect to DuckDB
    duck_conn = duckdb.connect('data/crypto.duckdb')
    
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        host="your-postgres-host",
        database="crypto",
        user="your-user",
        password="your-password"
    )
    
    # Migrate tables
    tables = ['raw.crypto_prices', 'staging.stg_crypto_prices', 'mart.fct_crypto_candlesticks']
    
    for table in tables:
        print(f"Migrating {table}...")
        
        # Read from DuckDB
        df = duck_conn.execute(f"SELECT * FROM {table}").pl()
        
        # Write to PostgreSQL
        df.write_database(
            table_name=table.replace('.', '_'),
            connection=pg_conn,
            if_table_exists='replace'
        )
    
    print("Migration complete!")

if __name__ == "__main__":
    migrate_data()
```

#### 3. Update Configuration

```yaml
# config/production.yaml
database:
  type: postgresql
  host: your-postgres-host
  port: 5432
  database: crypto
  user: your-user
  password: your-password
  sslmode: require

api:
  host: 0.0.0.0
  port: 8000
  workers: 4
  log_level: info

dagster:
  run_storage:
    module: dagster_postgres.run_storage
    class: PostgresRunStorage
    config:
      postgres_db:
        username: your-user
        password: your-password
        hostname: your-postgres-host
        db_name: dagster
        port: 5432
```

---

## 🔧 Production Configuration

### Environment Variables

```bash
# Production environment variables
export DATABASE_URL="postgresql://user:password@host:port/crypto"
export REDIS_URL="redis://host:port/0"
export API_HOST="0.0.0.0"
export API_PORT="8000"
export LOG_LEVEL="info"
export ENVIRONMENT="production"
export SECRET_KEY="your-secret-key"
export CORS_ORIGINS="https://your-domain.com"
export RATE_LIMIT_REQUESTS="100"
export RATE_LIMIT_WINDOW="60"
```

### Production Settings

#### FastAPI Production Server

```python
# api/production.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Crypto ELT Pipeline API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Rate limiting
app.state.limiter = limiter
```

#### Rate Limiting Configuration

The API includes configurable rate limiting for production environments:

```python
# Environment variables for rate limiting
API_RATE_LIMIT = int(os.getenv("API_RATE_LIMIT", "100"))      # Requests per period
API_RATE_PERIOD = int(os.getenv("API_RATE_PERIOD", "60"))     # Time period in seconds

# Test environment overrides
TEST_RATE_LIMIT = int(os.getenv("TEST_RATE_LIMIT", str(API_RATE_LIMIT)))
TEST_RATE_PERIOD = int(os.getenv("TEST_RATE_PERIOD", str(API_RATE_PERIOD)))

# Initialize rate limiter
rate_limiter = RateLimiter(requests=TEST_RATE_LIMIT, period=TEST_RATE_PERIOD)
```

**Production Rate Limiting Settings:**

```bash
# Production rate limits (adjust based on your needs)
export API_RATE_LIMIT=1000      # 1000 requests per period
export API_RATE_PERIOD=300      # 5 minute window

# Development/testing overrides
export TEST_RATE_LIMIT=10000    # Higher limits for testing
export TEST_RATE_PERIOD=60      # 1 minute window
```

**Rate Limiting Headers:**

All API responses include rate limiting information:

- `X-RateLimit-Limit`: Maximum requests allowed per period
- `X-RateLimit-Period`: Time period in seconds
- `X-RateLimit-Remaining`: Remaining requests in current period (if using advanced rate limiting)

**Rate Limit Exceeded Response:**

```json
{
  "detail": "Rate limit exceeded. Maximum 1000 requests per 300 seconds."
}
```

#### Streamlit Production

```python
# streamlit_dashboard/production.py
import streamlit as st
from streamlit_authenticator import Authenticate

# Authentication
authenticator = Authenticate(
    credentials=st.secrets["credentials"],
    cookie_name="crypto_dashboard",
    cookie_key="crypto_dashboard_key",
    cookie_expiry_days=30
)

# Login
name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    st.write(f'Welcome *{name}*')
    # Dashboard content
elif authentication_status == False:
    st.error('Username/password is incorrect')
elif authentication_status == None:
    st.warning('Please enter your username and password')
```

---

## 📊 Monitoring and Observability

### Logging

```python
# src/crypto_elt_pipeline/logging_config.py
import logging
import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Metrics

```python
# src/crypto_elt_pipeline/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Metrics
pipeline_duration = Histogram('pipeline_duration_seconds', 'Pipeline execution time')
pipeline_success = Counter('pipeline_success_total', 'Successful pipeline runs')
pipeline_failure = Counter('pipeline_failure_total', 'Failed pipeline runs')
data_quality_gauge = Gauge('data_quality_score', 'Data quality score')

def track_pipeline_execution(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            pipeline_success.inc()
            return result
        except Exception as e:
            pipeline_failure.inc()
            raise
        finally:
            pipeline_duration.observe(time.time() - start_time)
    return wrapper
```

### Health Checks

```python
# api/health.py
from fastapi import APIRouter, HTTPException
import duckdb
import psycopg2
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health_check():
    """Comprehensive health check."""
    try:
        # Database connectivity
        if DATABASE_TYPE == "duckdb":
            conn = duckdb.connect(str(DUCKDB_PATH))
            conn.execute("SELECT 1").fetchone()
        else:
            conn = psycopg2.connect(DATABASE_URL)
            conn.cursor().execute("SELECT 1").fetchone()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "version": "1.0.0"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

@router.get("/health/database")
async def database_health():
    """Database-specific health check."""
    try:
        # Check table counts
        if DATABASE_TYPE == "duckdb":
            conn = duckdb.connect(str(DUCKDB_PATH))
            tables = ["raw.crypto_prices", "staging.stg_crypto_prices", "mart.fct_crypto_candlesticks"]
        else:
            conn = psycopg2.connect(DATABASE_URL)
            tables = ["raw_crypto_prices", "stg_crypto_prices", "fct_crypto_candlesticks"]
        
        health = {}
        for table in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            health[table] = count
        
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database health check failed: {str(e)}")
```

---

## 🔐 Security Considerations

### Authentication and Authorization

```python
# api/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

security = HTTPBearer()

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
```

### Environment Security

```bash
# .env.production (never commit to version control)
DATABASE_URL="postgresql://user:password@host:port/crypto"
SECRET_KEY="your-super-secret-key"
JWT_ALGORITHM="HS256"
JWT_EXPIRATION_HOURS=24
SENTRY_DSN="https://your-sentry-dsn@sentry.io/project-id"
```

### SSL/TLS Configuration

```python
# api/ssl_config.py
import ssl

# SSL context for HTTPS
ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.load_cert_chain('path/to/cert.pem', 'path/to/key.pem')

# FastAPI with SSL
if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=443,
        ssl_keyfile="path/to/key.pem",
        ssl_certfile="path/to/cert.pem"
    )
```

---

## 🚀 CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install uv
        uv sync
    
    - name: Run tests
      run: uv run pytest tests/ -v
    
    - name: Build Docker image
      run: docker build -t crypto-elt-api:${{ github.sha }} .
    
    - name: Push to registry
      run: |
        echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
        docker push crypto-elt-api:${{ github.sha }}
    
    - name: Deploy to AWS ECS
      uses: aws-actions/amazon-ecs-deploy-task-definition@v1
      with:
        task-definition: task-definition.json
        service: crypto-api-service
        cluster: crypto-cluster
        wait-for-service-stability: true
```

### Deployment Scripts

```bash
#!/bin/bash
# deploy.sh

set -e

echo "🚀 Starting deployment..."

# Build and push Docker images
docker build -t crypto-elt-api:latest .
docker tag crypto-elt-api:latest your-registry/crypto-elt-api:latest
docker push your-registry/crypto-elt-api:latest

# Deploy to Kubernetes
kubectl apply -f k8s-deployment.yaml
kubectl rollout status deployment/crypto-api

# Run database migrations
kubectl exec -it $(kubectl get pods -l app=crypto-api -o name | head -1) -- python migrate_data.py

# Health check
curl -f http://localhost:8000/health || exit 1

echo "✅ Deployment successful!"
```

---

## 📈 Performance Optimization

### Database Optimization

```sql
-- PostgreSQL indexes for optimal performance
CREATE INDEX CONCURRENTLY idx_crypto_prices_coin_recorded_at 
ON raw.crypto_prices (coin, recorded_at);

CREATE INDEX CONCURRENTLY idx_crypto_prices_recorded_at 
ON raw.crypto_prices (recorded_at);

CREATE INDEX CONCURRENTLY idx_candlesticks_coin_trade_date 
ON mart.fct_crypto_candlesticks (coin, trade_date);

-- Analyze tables for query optimization
ANALYZE raw.crypto_prices;
ANALYZE staging.stg_crypto_prices;
ANALYZE mart.fct_crypto_candlesticks;
```

### Caching Strategy

```python
# src/crypto_elt_pipeline/cache.py
import redis
import json
from functools import wraps
from datetime import timedelta

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cache_result(ttl_minutes=30):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            redis_client.setex(
                cache_key, 
                timedelta(minutes=ttl_minutes), 
                json.dumps(result, default=str)
            )
            return result
        return wrapper
    return decorator

# Usage
@cache_result(ttl_minutes=60)
def get_candlestick_data(coin, days):
    # Expensive database query
    return query_database(coin, days)
```

### Load Balancing

```yaml
# k8s-load-balancer.yaml
apiVersion: v1
kind: Service
metadata:
  name: crypto-api-service
spec:
  type: LoadBalancer
  selector:
    app: crypto-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: crypto-api-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.crypto-elt.com
    secretName: crypto-api-tls
  rules:
  - host: api.crypto-elt.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: crypto-api-service
            port:
              number: 80
```

---

## 📚 Related Documentation

- [System Design](system-design.md) - Architecture overview
- [Data Modeling](data-modeling.md) - Database structure and transformations
- [Setup Guide](setup-guide.md) - Local development setup
- [Testing Guide](testing.md) - Testing strategy

---

## 🤝 Support

For deployment-related questions:

1. **Check deployment logs**: `docker-compose logs -f`
2. **Monitor health**: `curl http://localhost:8000/health`
3. **Database status**: Check database connectivity and performance
4. **Create an issue**: [GitHub Issues](https://github.com/mohamed-boughattas/crypto-elt-pipeline/issues)

---

**[← Back to Documentation Index](index.md)**
