"""Configuration module for FastAPI application."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "sqlite:///./data/ai_product_intelligence.db"
    
    # API
    api_title: str = "AI Product Intelligence & Trust Engine"
    api_version: str = "0.1.0"
    api_description: str = "Industrial product data extraction, normalization, and trust scoring"
    
    # OpenAI-compatible LLM provider
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    openai_model: str = "gpt-5-mini"
    llm_provider: str = "openai_compatible"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 0
    # Keep provider requests bounded; the configured provider becomes slow as product count grows.
    llm_batch_size: int = 2
    
    # Phase 3B conflict policy. Comma-separated values allow deployment-specific tuning
    # without hardcoding a source selection or automatic conflict resolution policy.
    conflict_critical_attributes: str = "sku,product id,model number,part number,catalog number,mpn,manufacturer,brand"
    conflict_high_attributes: str = "voltage,power,pressure,dimensions,material,current,frequency,speed,efficiency,temperature,ip rating,frame size,weight"
    conflict_medium_attributes: str = "category,series,mounting type,description"
    conflict_source_authority: str = "manufacturer_documentation,manufacturer_website,structured_catalog,distributor,unknown"

    # Phase 4 evaluation paths and transparent baseline quality policy. These settings are
    # intentionally configurable because the supplied dataset has raw inputs only, not an
    # official Unilog delivery-format specification or controlled vocabulary workbook.
    evaluation_input_dataset_path: str = "data/evaluation/Unihack_SampleDataset-Input.csv"
    evaluation_expected_dataset_path: Optional[str] = None
    evaluation_title_max_length: int = 255
    evaluation_description_max_length: int = 4000
    evaluation_allowed_uoms: str = "v,kv,a,ma,w,kw,mw,hz,khz,mhz,mm,cm,m,m2,mm2,kg,g,lb,l,n,m/s,rpm,c,f,bar,psi,pa,mpa,ohm,khm,mo,db,dbm,percent,%"

    # Phase 5 reference data is user-supplied and retained separately from ingestion sources.
    reference_data_directory: str = "data/reference_data"
    
    # Phase 7 discovery. Discovery is disabled by default until a deployment configures a
    # supported provider. Limits are intentionally strict to prevent unbounded crawling.
    discovery_provider: str = "none"
    discovery_provider_api_key: Optional[str] = None
    discovery_max_queries_per_product: int = 4
    discovery_max_results_per_query: int = 5
    discovery_max_sources_per_product: int = 8
    discovery_max_fetches_per_run: int = 5
    discovery_fetch_timeout_seconds: float = 15.0
    discovery_max_response_bytes: int = 2_000_000
    discovery_max_redirects: int = 3
    discovery_min_identity_score: float = 0.60

    # Production/runtime controls. Comma-separated origins are parsed by the app at startup.
    debug: bool = False
    environment: str = "development"
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_url: Optional[str] = None
    max_upload_size_bytes: int = 25 * 1024 * 1024
    request_timeout_seconds: float = 120.0
    logging_level: str = "INFO"
    enable_docs: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


settings = Settings()
