from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from mcp_server.openmrs_client import client

@asynccontextmanager
async def lifespan(server: FastMCP):
    yield
    await client.aclose()

mcp = FastMCP("openmrs-mcp-server",host="0.0.0.0",port=8091,lifespan=lifespan)