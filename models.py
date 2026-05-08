"""Pydantic models for FastAPI request/response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any, Union


class AzureConfig(BaseModel):
    """Azure OpenAI configuration."""
    api_key: str
    endpoint: str
    deployment: str
    api_version: str


class Features(BaseModel):
    """Feature flags for a product."""
    real_time_protection: bool
    firewall: bool
    vpn: bool
    password_manager: bool
    parental_controls: bool
    dark_web_monitoring: bool
    identity_theft_protection: bool
    anti_ransomware: bool
    cloud_backup: bool
    webcam_protection: bool
    safe_browsing: bool
    email_protection: bool


class CompetitorData(BaseModel):
    """Data for a single competitor product."""
    competitor: str
    product: str
    tier: str
    price_usd_year: Union[float, int, str] = 0
    original_price_usd_year: Union[float, int, str] = 0
    devices: Union[int, str] = "Unlimited"
    rating: Union[float, int, str] = 0
    url: str
    verdict: str
    features: Features
    pros: List[str]
    cons: List[str]


class ComparisonResponse(BaseModel):
    """Response containing comparison data."""
    query: str
    data: List[CompetitorData]
    summary: Dict[str, Any]


class ConfigResponse(BaseModel):
    """Response confirming config was saved."""
    status: str
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
