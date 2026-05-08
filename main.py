"""FastAPI application for McAfee Competitor Intelligence."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AuthenticationError
import os
import logging
from dotenv import load_dotenv

from models import AzureConfig, ComparisonResponse, ConfigResponse, HealthResponse
from services import call_azure, get_mcafee_products, calculate_summary

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()

# ── FastAPI Setup ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="McAfee Competitor Intelligence API",
    description="Compare McAfee products with competitors using Azure OpenAI",
    version="1.0.0",
)

# ── CORS Configuration ─────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "1.0.0"
    }


@app.get("/products")
async def list_products():
    """Get list of available McAfee products."""
    return {
        "products": get_mcafee_products()
    }


class CompareRequest(BaseModel):
    """Request body for comparison endpoint."""
    product: str
    config: AzureConfig


@app.post("/compare", response_model=ComparisonResponse)
async def compare_products(request: CompareRequest):
    """
    Compare a McAfee product with competitors.
    
    - **product**: McAfee product name or custom product description
    - **config**: Azure OpenAI configuration (api_key, endpoint, deployment, api_version)
    """
    product = request.product
    config = request.config
    
    if not product.strip():
        raise HTTPException(status_code=400, detail="Product name cannot be empty")

    try:
        logger.info(f"Starting comparison for product: {product}")
        data, raw = call_azure(
            product=product,
            api_key=config.api_key,
            endpoint=config.endpoint,
            deployment=config.deployment,
            api_version=config.api_version,
        )
        logger.info(f"Azure response received. Parsed data: {data is not None}")
        logger.debug(f"Raw response (first 500 chars): {raw[:500] if raw else 'None'}")
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Invalid Azure OpenAI API key."
        )
    except Exception as e:
        logger.error(f"Error calling Azure: {type(e).__name__}: {e}")
        error_msg = str(e)
        if "404" in error_msg:
            raise HTTPException(
                status_code=404,
                detail="Resource not found. Check deployment name and API version."
            )
        raise HTTPException(status_code=500, detail=f"Error: {error_msg}")

    if not data:
        logger.warning("Could not parse JSON from response")
        raise HTTPException(
            status_code=422,
            detail="Could not parse JSON response from Azure OpenAI"
        )

    logger.info(f"Successfully parsed {len(data)} competitor entries")
    summary = calculate_summary(data)

    return {
        "query": product,
        "data": data,
        "summary": summary,
    }


@app.get("/debug/config")
async def debug_config():
    """Debug endpoint to check if .env is loaded."""
    return {
        "api_key_loaded": bool(os.getenv("AZURE_OPENAI_API_KEY")),
        "endpoint_loaded": bool(os.getenv("AZURE_OPENAI_ENDPOINT")),
        "deployment_loaded": bool(os.getenv("AZURE_OPENAI_DEPLOYMENT")),
        "api_version_loaded": bool(os.getenv("AZURE_OPENAI_API_VERSION")),
        "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", "NOT SET"),
        "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT", "NOT SET"),
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "NOT SET"),
    }


@app.post("/compare-with-env", response_model=ComparisonResponse)
async def compare_with_env(product: str):
    """Compare using credentials from .env file (for testing)."""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    
    if not all([api_key, endpoint, deployment]):
        raise HTTPException(
            status_code=400,
            detail="Missing environment variables. Check your .env file."
        )
    
    try:
        logger.info(f"Comparing '{product}' using .env credentials")
        data, raw = call_azure(
            product=product,
            api_key=api_key,
            endpoint=endpoint,
            deployment=deployment,
            api_version=api_version,
        )
        logger.info(f"Successfully parsed {len(data) if data else 0} entries")
    except Exception as e:
        logger.error(f"Error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    if not data:
        raise HTTPException(status_code=422, detail="Could not parse response from Azure")
    
    summary = calculate_summary(data)
    return {
        "query": product,
        "data": data,
        "summary": summary,
    }


@app.get("/api-versions")
async def get_api_versions():
    """Get list of supported Azure OpenAI API versions."""
    versions = [
        "2025-01-01-preview",
        "2024-12-01-preview",
        "2024-10-21",
        "2024-08-01-preview",
        "2024-05-01-preview",
        "2024-02-01",
    ]
    return {
        "versions": versions,
        "recommended": "2025-01-01-preview"
    }


@app.get("/features")
async def get_features():
    """Get list of security features tracked in comparisons."""
    features = [
        ("real_time_protection", "🛡️ Real-Time Protection"),
        ("firewall", "🔥 Firewall"),
        ("vpn", "🔒 VPN Included"),
        ("password_manager", "🔑 Password Manager"),
        ("parental_controls", "👨‍👩‍👧 Parental Controls"),
        ("dark_web_monitoring", "🕵️ Dark Web Monitoring"),
        ("identity_theft_protection", "🪪 Identity Theft Protection"),
        ("anti_ransomware", "💀 Anti-Ransomware"),
        ("cloud_backup", "☁️ Cloud Backup"),
        ("webcam_protection", "📷 Webcam Protection"),
        ("safe_browsing", "🌐 Safe Browsing"),
        ("email_protection", "📧 Email Protection"),
    ]
    return {
        "features": [{"key": k, "label": l} for k, l in features]
    }


# ── Root endpoint ──────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    """API documentation and quick start."""
    return {
        "name": "McAfee Competitor Intelligence API",
        "version": "1.0.0",
        "endpoints": {
            "GET /health": "Health check",
            "GET /products": "List available McAfee products",
            "GET /features": "List tracked security features",
            "GET /api-versions": "List supported Azure OpenAI API versions",
            "POST /compare": "Compare a product with competitors (requires config)",
        },
        "docs": "/docs",
        "redoc": "/redoc",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
