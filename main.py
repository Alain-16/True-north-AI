import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from core.config import get_settings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from agent.graph import build_graph
from psycopg_pool import AsyncConnectionPool
from features.chat.router import router
settings = get_settings()

async def _start_consumer():
    pass

async def _start_scheduler():
    pass


@asynccontextmanager
async def lifespan(app:FastAPI):
    conninfo = settings.database_url.replace("postgresql+asyncpg://","postgresql://")

    async with AsyncConnectionPool(conninfo=conninfo,kwargs={"autocommit":True}) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        app.state.graph = build_graph(checkpointer)

        consumer_task = asyncio.create_task(_start_consumer())
        scheduler_task = asyncio.create_task(_start_scheduler())

        yield

        consumer_task.cancel()
        scheduler_task.cancel()

        await asyncio.gather(consumer_task,scheduler_task,return_exceptions=True)


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
