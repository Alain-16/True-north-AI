
from mcp.server.fastmcp import FastMCP
from mcp_server.config import get_mcp_settings

settings = get_mcp_settings()


mcp = FastMCP("openmrs-mcp-server",host=settings.mcp_host,port=settings.mcp_port)