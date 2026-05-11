from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import AzureOpenAI
from tavily import TavilyClient
import os
from dotenv import load_dotenv
 
# Import your existing functions
from app1 import (
    fetch_vendor_content,
    extract_vendor_data,
    VENDOR_QUERIES,
    FEATURES,
)
 
load_dotenv()
 
app = FastAPI(title="McAfee Pricing API")
 
class CompareRequest(BaseModel):
    product: str
 
 
@app.post("/compare")
def compare_products(req: CompareRequest):
 
    # Load env config
    az_key = os.getenv("AZURE_OPENAI_API_KEY")
    az_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    az_deploy = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    az_ver = os.getenv("AZURE_OPENAI_API_VERSION")
    tavily_key = os.getenv("TAVILY_API_KEY")
 
    if not all([az_key, az_endpoint, az_deploy, az_ver, tavily_key]):
        raise HTTPException(status_code=500, detail="Missing environment variables")
 
    vendors = list(VENDOR_QUERIES.keys())
 
    tavily_client = TavilyClient(api_key=tavily_key)
    az_client = AzureOpenAI(
        api_key=az_key,
        azure_endpoint=az_endpoint,
        api_version=az_ver,
    )
 
    results = []
 
    for vendor in vendors:
        fetch_result = fetch_vendor_content(vendor, tavily_client)
 
        vendor_data = extract_vendor_data(
            vendor,
            fetch_result["content"],
            req.product,
            az_client,
            az_deploy,
        )
 
        results.append(vendor_data)
 
    return {
        "query_product": req.product,
        "competitors_compared": len(results),
        "results": results
    }

@app.get("/health")
def health_check():
    return {"status": "ok"}