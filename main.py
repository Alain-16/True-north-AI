import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import logging

from core.config import get_settings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent.graph import build_graph
from psycopg_pool import AsyncConnectionPool
from features.chat.router import router
from agent.mcp_client import mcp_client
from events.activemq_consumer import consumer
settings = get_settings()
logger = logging.getLogger(__name__)


async def _start_scheduler():
    pass


@asynccontextmanager
async def lifespan(app:FastAPI):
    conninfo = settings.database_url.replace("postgresql+asyncpg://","postgresql://")

    async with AsyncConnectionPool(conninfo=conninfo,kwargs={"autocommit":True}) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        app.state.graph = build_graph(checkpointer)

        await mcp_client.connect()

        loop = asyncio.get_running_loop()
        try:
            consumer.start(loop)
        except Exception:
            logger.exception("Could not start activemq consumer; events disabled")
        scheduler_task = asyncio.create_task(_start_scheduler())

        yield

        consumer.stop()
        scheduler_task.cancel()

        await asyncio.gather(scheduler_task,return_exceptions=True)

        await mcp_client.close()


app = FastAPI(
    title="TrueNorth-AI API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,

)

app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)   




Instrumentator().instrument(app).expose(app)

@app.get("/health",tags=["infrastructure"])
async def health_check():
    return JSONResponse({"status":"ok"})
