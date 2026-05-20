from mcp.server.fastmcp import FastMCP

mcp = FastMCP("openmrs-mcp-server",host="0.0.0.0",port=8091)

if __name__ == "__main__":
    mcp.run(transport="sse")