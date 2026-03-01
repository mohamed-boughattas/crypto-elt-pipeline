# 🚀 API Reference

REST API documentation for the Crypto ELT Pipeline.

---

## 📋 Overview

The Crypto ELT Pipeline provides a REST API for programmatic access to cryptocurrency market data. The API serves data from the Gold layer (`mart.fct_crypto_candlesticks`) and provides endpoints for:

- **Health checks** and system status
- **Coin discovery** and metadata
- **OHLC candlestick data** with technical indicators
- **Latest market data** for all cryptocurrencies

**Base URL**: `http://localhost:8000`

**API Documentation**: <http://localhost:8000/docs> (Auto-generated OpenAPI/Swagger UI)

---

## 🔗 Available Endpoints

### Health Check

#### `GET /health`

Health check endpoint to verify API and database status.

**Response:**

```json
{
  "status": "healthy",
  "database_path": "/path/to/crypto.duckdb",
  "timestamp": "2026-03-01T10:30:00Z"
}
```

**Example:**

```bash
curl http://localhost:8000/health
```

---

### Coin Discovery

#### `GET /api/v1/coins`

Get list of available cryptocurrencies.

**Response:**

```json
{
  "coins": [
    "bitcoin",
    "ethereum",
    "ripple",
    "solana",
    "cardano",
    "avalanche-2",
    "polkadot",
    "binancecoin",
    "chainlink",
    "dogecoin"
  ],
  "count": 10
}
```

**Example:**

```bash
curl http://localhost:8000/api/v1/coins
```

---

### Candlestick Data

#### `GET /api/v1/candlesticks/{coin}`

Get OHLC candlestick data for a specific cryptocurrency.

**Parameters:**

| Parameter    | Type    | Required | Default | Description                                 |
| ------------ | ------- | -------- | ------- | ------------------------------------------- |
| `coin`       | string  | Yes      | -       | Cryptocurrency identifier (e.g., "bitcoin") |
| `start_date` | date    | No       | -       | Start date filter (YYYY-MM-DD)              |
| `end_date`   | date    | No       | -       | End date filter (YYYY-MM-DD)                |
| `days`       | integer | No       | 30      | Number of days to return (1-365)            |

**Response:**

```json
[
  {
    "trade_date": "2026-03-01",
    "coin": "bitcoin",
    "open_price": 42500.0,
    "high_price": 43000.0,
    "low_price": 42000.0,
    "close_price": 42800.0,
    "daily_volume": 25000000000.0,
    "volatility_pct": 2.38,
    "samples_count": 24,
    "sma_7": 42650.0,
    "sma_25": 42400.0,
    "bb_middle": 42600.0,
    "bb_upper": 43200.0,
    "bb_lower": 42000.0,
    "bb_width": 2.81,
    "bb_position": 0.67,
    "daily_change_pct": 0.71,
    "price_range": 1000.0
  }
]
```

**Examples:**

```bash
# Get last 30 days for Bitcoin
curl "http://localhost:8000/api/v1/candlesticks/bitcoin"

# Get specific date range
curl "http://localhost:8000/api/v1/candlesticks/bitcoin?start_date=2026-02-01&end_date=2026-03-01"

# Get last 7 days
curl "http://localhost:8000/api/v1/candlesticks/bitcoin?days=7"
```

**Error Responses:**

```json
{
  "detail": "No data found for coin: invalid_coin"
}
```

---

### Latest Data

#### `GET /api/v1/latest`

Get the latest candlestick data for all cryptocurrencies.

**Response:**

```json
[
  {
    "trade_date": "2026-03-01",
    "coin": "bitcoin",
    "open_price": 42500.0,
    "high_price": 43000.0,
    "low_price": 42000.0,
    "close_price": 42800.0,
    "daily_volume": 25000000000.0,
    "volatility_pct": 2.38,
    "samples_count": 24,
    "sma_7": 42650.0,
    "sma_25": 42400.0,
    "bb_middle": 42600.0,
    "bb_upper": 43200.0,
    "bb_lower": 42000.0,
    "bb_width": 2.81,
    "bb_position": 0.67,
    "daily_change_pct": 0.71,
    "price_range": 1000.0
  }
]
```

**Example:**

```bash
curl http://localhost:8000/api/v1/latest
```

---

## 📊 Data Model

### Candlestick Data Structure

| Field              | Type    | Description                                            | Example       |
| ------------------ | ------- | ------------------------------------------------------ | ------------- |
| `trade_date`       | date    | Trading date (UTC)                                     | "2026-03-01"  |
| `coin`             | string  | Cryptocurrency identifier                              | "bitcoin"     |
| `open_price`       | number  | Opening price (first price of day)                     | 42500.0       |
| `high_price`       | number  | Highest price during day                               | 43000.0       |
| `low_price`        | number  | Lowest price during day                                | 42000.0       |
| `close_price`      | number  | Closing price (last price of day)                      | 42800.0       |
| `daily_volume`     | number  | Total trading volume                                   | 25000000000.0 |
| `volatility_pct`   | number  | Intraday volatility percentage                         | 2.38          |
| `samples_count`    | integer | Number of hourly samples aggregated                    | 24            |
| `sma_7`            | number  | 7-day simple moving average                            | 42650.0       |
| `sma_25`           | number  | 25-day simple moving average                           | 42400.0       |
| `bb_middle`        | number  | Bollinger Band middle band (20-day SMA)                | 42600.0       |
| `bb_upper`         | number  | Bollinger Band upper band                              | 43200.0       |
| `bb_lower`         | number  | Bollinger Band lower band                              | 42000.0       |
| `bb_width`         | number  | Bollinger Band width as percentage of middle band      | 2.81          |
| `bb_position`      | number  | Price position relative to Bollinger Bands (0-1 scale) | 0.67          |
| `daily_change_pct` | number  | Daily price change percentage                          | 0.71          |
| `price_range`      | number  | Absolute price range (high - low)                      | 1000.0        |

---

## 🔧 Usage Examples

### Python Client

```python
import requests
import pandas as pd

class CryptoAPIClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url

    def get_coins(self):
        """Get list of available coins."""
        response = requests.get(f"{self.base_url}/api/v1/coins")
        response.raise_for_status()
        return response.json()["coins"]

    def get_candlesticks(self, coin, days=30):
        """Get candlestick data for a coin."""
        params = {"days": days}
        response = requests.get(f"{self.base_url}/api/v1/candlesticks/{coin}", params=params)
        response.raise_for_status()
        return pd.DataFrame(response.json())

    def get_latest_data(self):
        """Get latest data for all coins."""
        response = requests.get(f"{self.base_url}/api/v1/latest")
        response.raise_for_status()
        return pd.DataFrame(response.json())

# Usage
client = CryptoAPIClient()

# Get available coins
coins = client.get_coins()
print(f"Available coins: {coins}")

# Get Bitcoin data
btc_data = client.get_candlesticks("bitcoin", days=30)
print(btc_data.head())

# Get latest data for all coins
latest_data = client.get_latest_data()
print(latest_data[["coin", "close_price", "volatility_pct"]])
```

### JavaScript/Node.js Client

```javascript
const axios = require("axios");

class CryptoAPIClient {
  constructor(baseUrl = "http://localhost:8000") {
    this.baseUrl = baseUrl;
  }

  async getCoins() {
    const response = await axios.get(`${this.baseUrl}/api/v1/coins`);
    return response.data.coins;
  }

  async getCandlesticks(coin, days = 30) {
    const response = await axios.get(
      `${this.baseUrl}/api/v1/candlesticks/${coin}`,
      {
        params: { days },
      },
    );
    return response.data;
  }

  async getLatestData() {
    const response = await axios.get(`${this.baseUrl}/api/v1/latest`);
    return response.data;
  }
}

// Usage
const client = new CryptoAPIClient();

async function main() {
  try {
    const coins = await client.getCoins();
    console.log("Available coins:", coins);

    const btcData = await client.getCandlesticks("bitcoin", 7);
    console.log("Bitcoin data:", btcData);

    const latestData = await client.getLatestData();
    console.log("Latest data:", latestData);
  } catch (error) {
    console.error("Error:", error.message);
  }
}

main();
```

### cURL Examples

```bash
# Check API health
curl -X GET "http://localhost:8000/health" -H "accept: application/json"

# Get coin list
curl -X GET "http://localhost:8000/api/v1/coins" -H "accept: application/json"

# Get Bitcoin candlesticks (last 30 days)
curl -X GET "http://localhost:8000/api/v1/candlesticks/bitcoin" -H "accept: application/json"

# Get Bitcoin candlesticks (specific date range)
curl -X GET "http://localhost:8000/api/v1/candlesticks/bitcoin?start_date=2026-02-01&end_date=2026-03-01" -H "accept: application/json"

# Get latest data for all coins
curl -X GET "http://localhost:8000/api/v1/latest" -H "accept: application/json"
```

---

## 🛡️ Error Handling

### HTTP Status Codes

| Status Code | Description                              |
| ----------- | ---------------------------------------- |
| `200`       | Success                                  |
| `400`       | Bad Request (invalid parameters)         |
| `404`       | Not Found (coin not available)           |
| `500`       | Internal Server Error                    |
| `503`       | Service Unavailable (database not ready) |

### Error Response Format

```json
{
  "detail": "Error description"
}
```

**Examples:**

```json
{
  "detail": "No data found for coin: invalid_coin"
}
```

```json
{
  "detail": "days must be between 1 and 365"
}
```

```json
{
  "detail": "Database connection failed"
}
```

---

## ⚡ Performance Considerations

### Rate Limiting

- **Default rate limiting**: 100 requests per 60 seconds per IP
- **Test environment**: Can be configured with environment variables
- **Rate limit headers**: `X-RateLimit-Limit` and `X-RateLimit-Period` included in responses
- **Rate limit exceeded**: Returns 429 status code with error message
- **Recommendation**: Implement exponential backoff for failed requests
- **Caching**: Consider implementing client-side caching for frequently accessed data

#### Environment Variables

For testing or development environments, rate limiting can be configured:

```bash
# Set custom rate limits for testing
export TEST_RATE_LIMIT=1000
export TEST_RATE_PERIOD=60

# Default values (used when TEST_* variables not set)
export API_RATE_LIMIT=100
export API_RATE_PERIOD=60
```

#### Rate Limit Headers

All API responses include rate limiting information:

```http
X-RateLimit-Limit: 100
X-RateLimit-Period: 60
```

#### Rate Limit Exceeded Response

```json
{
  "detail": "Rate limit exceeded. Maximum 100 requests per 60 seconds."
}
```

### Query Optimization

- **Date ranges**: Use specific date ranges for better performance
- **Days parameter**: Limit to reasonable ranges (1-365 days)
- **Coin selection**: Query specific coins rather than all data when possible

### Response Size

- **Large date ranges**: May return large datasets
- **Pagination**: Not implemented (returns all matching records)
- **Memory usage**: Consider streaming for very large responses

---

## 🔌 Integration Examples

### With Pandas (Python)

```python
import requests
import pandas as pd

def fetch_crypto_data(coin, days=30):
    """Fetch crypto data and return as pandas DataFrame."""
    url = f"http://localhost:8000/api/v1/candlesticks/{coin}"
    response = requests.get(url, params={"days": days})
    response.raise_for_status()

    df = pd.DataFrame(response.json())
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df.set_index('trade_date', inplace=True)

    return df

# Usage
btc_df = fetch_crypto_data('bitcoin', days=90)
print(btc_df.describe())

# Technical analysis
btc_df['price_change'] = btc_df['close_price'].pct_change()
btc_df['volatility'] = btc_df['volatility_pct'] / 100
print(f"Average daily return: {btc_df['price_change'].mean():.4f}")
print(f"Average volatility: {btc_df['volatility'].mean():.4f}")
```

### With Chart.js (Web)

```html
<!DOCTYPE html>
<html>
  <head>
    <title>Crypto Chart</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  </head>
  <body>
    <canvas id="cryptoChart" width="800" height="400"></canvas>

    <script>
      async function loadChartData() {
        const response = await fetch(
          "http://localhost:8000/api/v1/candlesticks/bitcoin?days=30",
        );
        const data = await response.json();

        const labels = data.map((d) => d.trade_date);
        const prices = data.map((d) => d.close_price);

        const ctx = document.getElementById("cryptoChart").getContext("2d");
        new Chart(ctx, {
          type: "line",
          data: {
            labels: labels,
            datasets: [
              {
                label: "Bitcoin Price (USD)",
                data: prices,
                borderColor: "#f7931a",
                backgroundColor: "rgba(247, 147, 26, 0.1)",
                tension: 0.4,
              },
            ],
          },
          options: {
            responsive: true,
            plugins: {
              title: {
                display: true,
                text: "Bitcoin Price - Last 30 Days",
              },
            },
          },
        });
      }

      loadChartData();
    </script>
  </body>
</html>
```

---

## 🚀 Deployment Considerations

### Production Deployment

When deploying the API to production:

1. **Security**: Add authentication and authorization
2. **Rate Limiting**: Implement request rate limiting
3. **Caching**: Add Redis or similar for response caching
4. **Monitoring**: Add logging and metrics collection
5. **Load Balancing**: Consider multiple API instances
6. **Database**: Use production database (PostgreSQL, etc.)

### Docker Deployment

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables

```bash
# Production settings
export DATABASE_URL="postgresql://user:password@host:port/db"
export API_HOST="0.0.0.0"
export API_PORT="8000"
export LOG_LEVEL="info"
```

---

## 📚 Related Documentation

- [System Design](system-design.md) - Architecture overview
- [Data Modeling](data-modeling.md) - Database structure and transformations
- [Setup Guide](setup-guide.md) - Installation and configuration
- [Testing Guide](testing.md) - Testing strategy

---

## 🤝 Support

For API-related questions or issues:

1. **Check the auto-generated docs**: <http://localhost:8000/docs>
2. **Review the OpenAPI schema**: <http://localhost:8000/openapi.json>
3. **Create an issue**: [GitHub Issues](https://github.com/mohamed-boughattas/crypto-elt-pipeline/issues)
4. **Join discussions**: [GitHub Discussions](https://github.com/mohamed-boughattas/crypto-elt-pipeline/discussions)

---

**[← Back to Documentation Index](index.md)**
