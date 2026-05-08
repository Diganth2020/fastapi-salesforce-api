# McAfee Competitor Intelligence API

A FastAPI-based REST API for comparing McAfee products with competitors using Azure OpenAI intelligence.

## 📋 What Changed

This is a **FastAPI conversion** of the original Streamlit application. Instead of a web UI, you now have a powerful REST API.

### Original (Streamlit):
- Web interface for configuration
- Interactive product selection
- Real-time dashboard rendering

### New (FastAPI):
- RESTful API endpoints
- JSON request/response
- Programmatic access
- Easy integration with other services
- Interactive OpenAPI documentation at `/docs`

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create a `.env` file in the root directory:

```env
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2025-01-01-preview
```

### 3. Run the API

```bash
python main.py
```

Or use Uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Access the API

- **Interactive Docs (Swagger):** http://localhost:8000/docs
- **ReDoc Documentation:** http://localhost:8000/redoc
- **API Base URL:** http://localhost:8000

---

## 📚 API Endpoints

### Get Health Status
```
GET /health
```
Check if the API is running.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

---

### List Available Products
```
GET /products
```
Get list of McAfee products you can compare.

**Response:**
```json
{
  "products": [
    "McAfee Total Protection",
    "McAfee LiveSafe",
    "McAfee AntiVirus Plus",
    ...
  ]
}
```

---

### Compare Products
```
POST /compare
```
Get competitor comparison data for a specific McAfee product.

**Request Body:**
```json
{
  "product": "McAfee Total Protection",
  "config": {
    "api_key": "your-azure-key",
    "endpoint": "https://your-resource.openai.azure.com/",
    "deployment": "your-deployment",
    "api_version": "2025-01-01-preview"
  }
}
```

**Response:**
```json
{
  "query": "McAfee Total Protection",
  "data": [
    {
      "competitor": "McAfee",
      "product": "McAfee Total Protection",
      "tier": "Premium",
      "price_usd_year": 49.99,
      "original_price_usd_year": 99.99,
      "devices": 5,
      "rating": 4.5,
      "url": "https://mcafee.com",
      "verdict": "Best all-in-one protection",
      "features": {
        "real_time_protection": true,
        "firewall": true,
        "vpn": true,
        ...
      },
      "pros": ["Excellent malware detection", "Includes VPN"],
      "cons": ["High renewal price"]
    },
    ...
  ],
  "summary": {
    "vendors_compared": 6,
    "lowest_price": 29.99,
    "lowest_price_vendor": "Avast",
    "most_features_vendor": "Norton",
    "most_features_count": 11,
    "mcafee_price": 49.99
  }
}
```

---

### Get Security Features List
```
GET /features
```
List all security features tracked in comparisons.

**Response:**
```json
{
  "features": [
    { "key": "real_time_protection", "label": "🛡️ Real-Time Protection" },
    { "key": "firewall", "label": "🔥 Firewall" },
    ...
  ]
}
```

---

### Get API Versions
```
GET /api-versions
```
Get list of supported Azure OpenAI API versions.

**Response:**
```json
{
  "versions": [
    "2025-01-01-preview",
    "2024-12-01-preview",
    ...
  ],
  "recommended": "2025-01-01-preview"
}
```

---

## 🔧 Project Structure

```
├── main.py           # FastAPI application & routes
├── models.py         # Pydantic request/response models
├── services.py       # Business logic & Azure OpenAI integration
├── requirements.txt  # Python dependencies
├── .env             # Environment variables (create this)
└── README.md        # This file
```

### Files Included

- **main.py** - FastAPI app with all endpoints
- **models.py** - Pydantic models for type safety
- **services.py** - Azure OpenAI integration logic
- **requirements.txt** - Updated with FastAPI dependencies

### Files Removed/Deprecated

- **app.py** - Original Streamlit application (no longer used)

---

## 🔐 Configuration

### Azure OpenAI Setup

1. Get credentials from Azure Portal:
   - Navigate to your OpenAI resource
   - Keys and Endpoint section
   - Copy API Key and Endpoint URL

2. Get deployment name from Azure AI Foundry:
   - Go to your project
   - Deployments section
   - Copy the deployment name (must match exactly)

3. Create `.env` file with credentials

---

## 📊 Example Usage with Python

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# Get available products
response = requests.get(f"{BASE_URL}/products")
products = response.json()["products"]
print(f"Available products: {products}")

# Compare a product
config = {
    "api_key": "your-key",
    "endpoint": "https://your-resource.openai.azure.com/",
    "deployment": "your-deployment",
    "api_version": "2025-01-01-preview"
}

response = requests.post(
    f"{BASE_URL}/compare",
    json={
        "product": "McAfee Total Protection",
        "config": config
    }
)

comparison = response.json()
print(json.dumps(comparison, indent=2))
```

---

## 📊 Example Usage with cURL

```bash
# Health check
curl http://localhost:8000/health

# List products
curl http://localhost:8000/products

# Compare products
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "product": "McAfee Total Protection",
    "config": {
      "api_key": "your-key",
      "endpoint": "https://your-resource.openai.azure.com/",
      "deployment": "your-deployment",
      "api_version": "2025-01-01-preview"
    }
  }'
```

---

## ⚠️ Error Handling

The API returns appropriate HTTP status codes:

- **200 OK** - Success
- **400 Bad Request** - Invalid parameters
- **401 Unauthorized** - Invalid Azure credentials
- **404 Not Found** - Resource not found
- **422 Unprocessable Entity** - Response parsing error
- **500 Internal Server Error** - Server error

---

## 🚀 Deployment

### Docker (Optional)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

Build and run:

```bash
docker build -t mcafee-api .
docker run -p 8000:8000 --env-file .env mcafee-api
```

---

## 📝 License

Same as original project

## 🤝 Support

For issues or questions, check the `/docs` endpoint for interactive API documentation.
