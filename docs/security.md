# 🔐 Security Guide

Security best practices and considerations for the Crypto ELT Pipeline.

---

## 🛡️ Overview

This document outlines security considerations for deploying and operating the Crypto ELT Pipeline in production environments. While the current implementation is designed for local development, this guide provides security recommendations for production deployments.

---

## 🔑 Authentication & Authorization

### API Security

#### 1. JWT Authentication

```python
# api/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta
import secrets

# Security configuration
SECRET_KEY = secrets.token_urlsafe(32)  # Generate secure secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

class TokenData:
    username: str
    scopes: list[str]

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token with expiration."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return user data."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return TokenData(username=username, scopes=payload.get("scopes", []))
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Protected endpoint example
@app.get("/api/v1/protected")
async def protected_endpoint(token_data: TokenData = Depends(verify_token)):
    """Example protected endpoint."""
    return {"message": f"Hello {token_data.username}", "scopes": token_data.scopes}
```

#### 2. OAuth2 Integration

```python
# api/oauth2.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.requests import Request
from starlette.responses import RedirectResponse

# OAuth2 configuration
config = Config('.env')
oauth = OAuth(config)

oauth.register(
    name='google',
    client_id=config('GOOGLE_CLIENT_ID'),
    client_secret=config('GOOGLE_CLIENT_SECRET'),
    client_kwargs={
        'scope': 'openid email profile',
        'response_type': 'code',
    },
    server_metadata_url='https://accounts.google.com/.well-known/openid_configuration'
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current user from OAuth2 token."""
    # Implementation depends on OAuth provider
    pass
```

### Dashboard Authentication

#### Streamlit Authentication

```python
# streamlit_dashboard/auth.py
import streamlit as st
from streamlit_authenticator import Authenticate
import yaml
from pathlib import Path

def load_auth_config():
    """Load authentication configuration from secure location."""
    config_path = Path(".streamlit/auth.yaml")
    if not config_path.exists():
        st.error("Authentication configuration not found")
        st.stop()
    
    with open(config_path) as file:
        config = yaml.load(file, Loader=yaml.SafeLoader)
    
    return config

def setup_authentication():
    """Setup Streamlit authentication."""
    config = load_auth_config()
    
    authenticator = Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        config['preauthorized']
    )
    
    name, authentication_status, username = authenticator.login('Login', 'main')
    
    if authentication_status:
        st.session_state['name'] = name
        st.session_state['authentication_status'] = authentication_status
        st.session_state['username'] = username
        return True
    elif authentication_status == False:
        st.error('Username/password is incorrect')
        return False
    elif authentication_status == None:
        st.warning('Please enter your username and password')
        return False

def logout():
    """Handle logout."""
    authenticator = st.session_state.get('authenticator')
    if authenticator:
        authenticator.logout('Logout', 'main')
```

---

## 🔒 Data Security

### Database Security

#### 1. Connection Security

```python
# src/crypto_elt_pipeline/database_security.py
import os
from urllib.parse import quote_plus

def get_secure_database_url():
    """Get secure database connection URL."""
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'crypto')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    
    if not all([db_user, db_password]):
        raise ValueError("Database credentials not configured")
    
    # URL encode password to handle special characters
    encoded_password = quote_plus(db_password)
    
    # PostgreSQL with SSL
    return f"postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?sslmode=require"

def validate_database_connection():
    """Validate database connection security."""
    try:
        import psycopg2
        conn = psycopg2.connect(get_secure_database_url())
        
        # Check SSL connection
        with conn.cursor() as cur:
            cur.execute("SELECT ssl_is_used();")
            ssl_used = cur.fetchone()[0]
            
        if not ssl_used:
            raise ValueError("SSL connection required")
            
        conn.close()
        return True
    except Exception as e:
        raise ValueError(f"Database security validation failed: {e}")
```

#### 2. Data Encryption

```python
# src/crypto_elt_pipeline/encryption.py
from cryptography.fernet import Fernet
import os

class DataEncryptor:
    def __init__(self):
        self.key = os.getenv('ENCRYPTION_KEY')
        if not self.key:
            self.key = Fernet.generate_key()
            # In production, store this key securely
        self.cipher_suite = Fernet(self.key)
    
    def encrypt_data(self, data: str) -> bytes:
        """Encrypt sensitive data."""
        return self.cipher_suite.encrypt(data.encode())
    
    def decrypt_data(self, encrypted_data: bytes) -> str:
        """Decrypt sensitive data."""
        return self.cipher_suite.decrypt(encrypted_data).decode()

# Usage
encryptor = DataEncryptor()
encrypted_api_key = encryptor.encrypt_data("your-api-key")
```

### API Security Headers

```python
# api/security_headers.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response

def setup_security(app: FastAPI):
    """Setup security middleware."""
    
    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://your-domain.com"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)
```

---

## 🔐 Environment Security

### Environment Variables Management

#### 1. Secure Configuration

```bash
# .env.production (never commit to version control)
# Database
DATABASE_URL="postgresql://user:password@host:port/crypto?sslmode=require"

# Authentication
SECRET_KEY="your-super-secret-key-here"
JWT_ALGORITHM="HS256"
JWT_EXPIRATION_HOURS=24

# API Security
CORS_ORIGINS="https://your-domain.com"
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# Monitoring
SENTRY_DSN="https://your-sentry-dsn@sentry.io/project-id"

# Encryption
ENCRYPTION_KEY="your-encryption-key-here"

# External APIs
COINGECKO_API_KEY="your-api-key-here"
```

#### 2. Docker Secrets

```yaml
# docker-compose.secrets.yml
version: '3.8'

services:
  api:
    build: .
    secrets:
      - db_password
      - jwt_secret
      - encryption_key

secrets:
  db_password:
    file: ./secrets/db_password.txt
  jwt_secret:
    file: ./secrets/jwt_secret.txt
  encryption_key:
    file: ./secrets/encryption_key.txt
```

#### 3. Kubernetes Secrets

```yaml
# k8s-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: crypto-secrets
type: Opaque
stringData:
  database-url: "postgresql://user:password@host:port/crypto"
  jwt-secret: "your-jwt-secret"
  encryption-key: "your-encryption-key"
  coingecko-api-key: "your-api-key"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crypto-api
spec:
  template:
    spec:
      containers:
      - name: api
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: crypto-secrets
              key: database-url
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: crypto-secrets
              key: jwt-secret
```

---

## 🚨 Rate Limiting & DDoS Protection

### API Rate Limiting

```python
# api/rate_limiting.py
from fastapi import FastAPI, Request, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis
from datetime import timedelta

# Redis connection for rate limiting
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=os.getenv('REDIS_PORT', 6379),
    db=0,
    decode_responses=True
)

# Rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379/0"
)

def setup_rate_limiting(app: FastAPI):
    """Setup rate limiting for the API."""
    
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        return HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later.",
            headers={"Retry-After": str(exc.retry_after)},
        )
    
    # Apply rate limits to endpoints
    @app.get("/api/v1/candlesticks/{coin}")
    @limiter.limit("100/minute")
    async def get_candlesticks(coin: str, days: int = 30):
        # Endpoint implementation
        pass
    
    @app.get("/api/v1/latest")
    @limiter.limit("50/minute")
    async def get_latest():
        # Endpoint implementation
        pass
```

### IP Whitelisting

```python
# api/ip_whitelist.py
from fastapi import Request, HTTPException
from typing import List
import ipaddress

class IPWhitelistMiddleware:
    def __init__(self, allowed_ips: List[str]):
        self.allowed_ips = [ipaddress.ip_network(ip) for ip in allowed_ips]
    
    async def __call__(self, request: Request, call_next):
        client_ip = request.client.host
        
        # Check if IP is allowed
        is_allowed = any(ipaddress.ip_address(client_ip) in network for network in self.allowed_ips)
        
        if not is_allowed:
            raise HTTPException(status_code=403, detail="IP address not allowed")
        
        response = await call_next(request)
        return response

# Usage
allowed_ips = ["192.168.1.0/24", "10.0.0.0/8"]
app.add_middleware(IPWhitelistMiddleware, allowed_ips=allowed_ips)
```

---

## 🔍 Monitoring & Logging Security

### Secure Logging

```python
# src/crypto_elt_pipeline/secure_logging.py
import logging
import json
from datetime import datetime
import secrets

class SecureLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create handler
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_access(self, request, user_id=None, action=None):
        """Log API access securely."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "ip": request.client.host,
            "user_id": user_id,
            "action": action,
            "endpoint": request.url.path,
            "method": request.method,
            "request_id": secrets.token_hex(8)
        }
        
        # Remove sensitive data before logging
        self.logger.info(f"API Access: {json.dumps(log_data)}")
    
    def log_security_event(self, event_type, details):
        """Log security events."""
        security_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "details": details,
            "severity": "HIGH" if event_type in ["AUTH_FAILURE", "UNAUTHORIZED_ACCESS"] else "MEDIUM"
        }
        
        self.logger.warning(f"Security Event: {json.dumps(security_log)}")

# Usage
secure_logger = SecureLogger("crypto_api")

@app.get("/api/v1/candlesticks/{coin}")
async def get_candlesticks(request: Request, coin: str):
    secure_logger.log_access(request, action="get_candlesticks")
    # Endpoint implementation
```

### Audit Trail

```python
# src/crypto_elt_pipeline/audit.py
import sqlite3
from datetime import datetime
from typing import Optional

class AuditTrail:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize audit database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id TEXT,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    ip_address TEXT,
                    success BOOLEAN NOT NULL,
                    details TEXT
                )
            """)
    
    def log_action(self, user_id: Optional[str], action: str, resource: str, 
                   ip_address: str, success: bool, details: Optional[str] = None):
        """Log user action."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO audit_log (timestamp, user_id, action, resource, ip_address, success, details)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.utcnow().isoformat(), user_id, action, resource, ip_address, success, details))
    
    def get_audit_trail(self, user_id: Optional[str] = None, action: Optional[str] = None):
        """Get audit trail."""
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        query += " ORDER BY timestamp DESC LIMIT 1000"
        
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(query, params).fetchall()

# Usage
audit = AuditTrail("data/audit.db")
audit.log_action("user123", "GET", "/api/v1/candlesticks/bitcoin", "192.168.1.100", True)
```

---

## 🛡️ Vulnerability Management

### Input Validation

```python
# api/validation.py
from fastapi import Query
from pydantic import BaseModel, validator
from typing import Optional
from datetime import date

class CandlestickRequest(BaseModel):
    coin: str = Query(..., description="Cryptocurrency identifier")
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)")
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)")
    days: Optional[int] = Query(None, ge=1, le=365, description="Number of days (1-365)")
    
    @validator('coin')
    def validate_coin(cls, v):
        """Validate cryptocurrency identifier."""
        valid_coins = ["bitcoin", "ethereum", "ripple", "solana", "cardano", 
                      "avalanche-2", "polkadot", "binancecoin", "chainlink", "dogecoin"]
        if v not in valid_coins:
            raise ValueError(f"Invalid coin. Must be one of: {', '.join(valid_coins)}")
        return v
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate date range."""
        start_date = values.get('start_date')
        if start_date and v and start_date > v:
            raise ValueError("start_date must be before end_date")
        return v

# Usage in endpoint
@app.get("/api/v1/candlesticks/{coin}")
async def get_candlesticks(request: CandlestickRequest):
    # Validation is automatic with Pydantic
    pass
```

### SQL Injection Prevention

```python
# src/crypto_elt_pipeline/database.py
import duckdb
from typing import List, Dict, Any

class SecureDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def execute_query(self, query: str, params: Dict[str, Any] = None):
        """Execute parameterized query safely."""
        with duckdb.connect(self.db_path) as conn:
            if params:
                # Use parameterized queries to prevent SQL injection
                return conn.execute(query, params).fetchall()
            else:
                return conn.execute(query).fetchall()
    
    def get_candlesticks(self, coin: str, days: int = 30):
        """Get candlestick data with parameterized query."""
        query = """
            SELECT * FROM mart.fct_crypto_candlesticks 
            WHERE coin = ? AND trade_date >= CURRENT_DATE - INTERVAL '? days'
            ORDER BY trade_date DESC
        """
        return self.execute_query(query, (coin, days))

# Usage
db = SecureDatabase("data/crypto.duckdb")
data = db.get_candlesticks("bitcoin", 30)
```

---

## 🔒 SSL/TLS Configuration

### HTTPS Setup

```python
# api/ssl_config.py
import ssl
import uvicorn

def create_ssl_context():
    """Create SSL context for HTTPS."""
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain('path/to/cert.pem', 'path/to/key.pem')
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # For development, use CERT_REQUIRED in production
    return context

def run_with_ssl():
    """Run FastAPI with SSL."""
    ssl_context = create_ssl_context()
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=443,
        ssl_keyfile="path/to/key.pem",
        ssl_certfile="path/to/cert.pem"
    )
```

### Certificate Management

```bash
# Generate self-signed certificate for development
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# For production, use Let's Encrypt
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com
```

---

## 🚨 Incident Response

### Security Monitoring

```python
# src/crypto_elt_pipeline/security_monitor.py
import time
from collections import defaultdict
from typing import Dict, List

class SecurityMonitor:
    def __init__(self):
        self.failed_attempts = defaultdict(list)
        self.blocked_ips = set()
        self.alert_threshold = 5
        self.block_duration = 300  # 5 minutes
    
    def check_authentication_failure(self, ip: str):
        """Monitor authentication failures."""
        now = time.time()
        
        # Clean old attempts
        self.failed_attempts[ip] = [
            attempt_time for attempt_time in self.failed_attempts[ip]
            if now - attempt_time < self.block_duration
        ]
        
        # Add current attempt
        self.failed_attempts[ip].append(now)
        
        # Check threshold
        if len(self.failed_attempts[ip]) >= self.alert_threshold:
            self.blocked_ips.add(ip)
            self.send_security_alert(ip, "Multiple authentication failures")
            return True
        
        return False
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked."""
        return ip in self.blocked_ips
    
    def send_security_alert(self, ip: str, message: str):
        """Send security alert."""
        # Implementation depends on alerting system
        print(f"SECURITY ALERT: {message} from IP {ip}")

# Usage in authentication
monitor = SecurityMonitor()

@app.post("/api/v1/auth/login")
async def login(request: Request, credentials: LoginCredentials):
    client_ip = request.client.host
    
    if monitor.is_ip_blocked(client_ip):
        raise HTTPException(status_code=429, detail="Too many failed attempts")
    
    # Authentication logic
    if not authenticate(credentials):
        if monitor.check_authentication_failure(client_ip):
            raise HTTPException(status_code=429, detail="Too many failed attempts")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Successful login
    return {"message": "Login successful"}
```

---

## 📋 Security Checklist

### Pre-Deployment

- [ ] **Environment Variables**: All secrets stored securely (not in code)
- [ ] **Database Security**: SSL/TLS enabled, strong passwords
- [ ] **API Security**: Authentication implemented, rate limiting configured
- [ ] **CORS**: Properly configured for allowed origins
- [ ] **SSL/TLS**: HTTPS enforced, valid certificates
- [ ] **Input Validation**: All inputs validated and sanitized
- [ ] **Logging**: Security events logged, sensitive data excluded
- [ ] **Monitoring**: Security monitoring and alerting configured

### Production

- [ ] **Regular Updates**: Dependencies and security patches up to date
- [ ] **Access Control**: Principle of least privilege enforced
- [ ] **Backup Security**: Encrypted backups with secure storage
- [ ] **Network Security**: Firewall rules and network segmentation
- [ ] **Incident Response**: Security incident response plan in place
- [ ] **Security Audits**: Regular security assessments and penetration testing

---

## 🚨 Emergency Procedures

### Security Breach Response

1. **Immediate Actions**:
   - Isolate affected systems
   - Preserve evidence
   - Notify security team

2. **Investigation**:
   - Analyze logs and audit trails
   - Identify scope and impact
   - Determine root cause

3. **Remediation**:
   - Patch vulnerabilities
   - Reset compromised credentials
   - Update security controls

4. **Recovery**:
   - Restore from clean backups
   - Monitor for residual threats
   - Update incident response procedures

---

## 📚 Security Resources

### External References

- [OWASP Top 10](https://owasp.org/Top10/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Controls](https://www.cisecurity.org/controls)
- [FastAPI Security Guide](https://fastapi.tiangolo.com/advanced/security/)

### Tools & Libraries

- **Authentication**: Authlib, PyJWT, python-multipart
- **Encryption**: cryptography, pycryptodome
- **Rate Limiting**: slowapi, redis
- **Monitoring**: structlog, sentry-sdk
- **Security Headers**: fastapi-security

---

## 🤝 Security Support

For security-related questions or incident reporting:

1. **Security Issues**: [GitHub Security Advisories](https://github.com/mohamed-boughattas/crypto-elt-pipeline/security)
2. **Vulnerability Reports**: Email <security@your-organization.com>
3. **Security Discussions**: [GitHub Discussions](https://github.com/mohamed-boughattas/crypto-elt-pipeline/discussions)

---

**[← Back to Documentation Index](index.md)**
