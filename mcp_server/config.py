from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


    openmrs_base_url: str
    openmrs_username: str
    openmrs_password: str

@lru_cache()
def get_mcp_settings()-> MCPSettings:
    return MCPSettings()