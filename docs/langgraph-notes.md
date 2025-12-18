# LangGraph Orchestration Notes

## Overview

This document describes the LangGraph orchestration skeleton for the multi-agent AI DJ planning system. It outlines the graph structure, node responsibilities, state schema, and streaming of updates for WebSocket event emission.

## Exact Imports Used

- `from langgraph.graph import StateGraph, START, END`

## DJState Schema Type

Defined as TypedDict classes:

```python
class NowPlayingSegment(TypedDict):
    track_id: str
    start_time: float
    duration: float

class DecisionStep(TypedDict):
    step: str
    detail: str

class DJState(TypedDict):
    now_playing: List[NowPlayingSegment]
    decision_trace: List[DecisionStep]
```

## LangGraph DJ Planning Graph Construction

The graph is constructed using the current StateGraph API:

```python
builder = StateGraph(DJState)
builder.add_node("bootstrap", bootstrap)
builder.add_edge(START, "bootstrap")
builder.add_edge("bootstrap", END)
graph = builder.compile()
```

Stub nodes are used for the various agents and tools.

## How DJLoop Calls the Graph

The DJLoop background task calls:

```python
await graph.ainvoke({"now_playing": [], "decision_trace": []})
```

This runs the graph asynchronously with an initial empty DJState.

## Startup Behavior and Graceful Degradation

- If LangGraph is not installed or graph compilation fails, the DJ planning graph is not created.
- The backend logs a warning but continues serving health endpoints without crashing.
- The DJLoop background task skips graph execution but keeps running a safe idle loop.

## Current Status

- Backend application starts cleanly with no errors related to LangGraph.
- LangGraph DJ planning graph compiles and runs stub node logic safely.
- DJLoop runs continuously in the background calling the graph asynchronously.
- WebSocket event streaming from LangGraph is stubbed but ready for future implementation.

---

This ensures the backend starts cleanly even with missing or incompatible LangGraph dependencies or runtime errors and lays a solid foundation for further DJ multi-agent orchestration work.
