from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding ="utf-8",
        extra="ignore"
    )

    mcp_server_url: str
    database_url: str

    anthropic_api_key: str

    meta_whatsapp_token: str
    meta_app_secret:str
    whatsapp_phone_number_id:str
    whatsapp_verify_token:str | None = None

    openmrs_base_url:str
    openmrs_username:str
    openmrs_password:str

    activemq_url:str
    activemq_username:str
    activemq_password:str

    langchain_api_key: str | None = None
    langchain_tracing_v2: bool = False
    langchain_project: str = "TrueNorth-agent"

    openai_api_key:str

    otp_expiry_minutes:int=10
    reminder_scan_interval_seconds:int=60
    rag_confidence_threshold:float=0.75
    default_country_code: str = "250"
    debug:bool=False

@lru_cache()
def get_settings() -> Settings:
    return Settings()
