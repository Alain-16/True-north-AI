import pytest
from langgraph.checkpoint.memory import MemorySaver
from agent.graph import build_graph


@pytest.fixture
def graph():
      # Fresh MemorySaver per test — no state leaks between tests
      return build_graph(checkpointer=MemorySaver())