"""FastAPI Server with Agent-to-Agent (A2A) Protocol integration."""
import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from app.agent import root_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("it-helpdesk-assistant.api")

app = FastAPI(
    title="IT Helpdesk AI Assistant API",
    description="FastAPI service hosting Google ADK IT Helpdesk Agent with A2A protocol support.",
    version="0.1.0"
)


class ChatRequest(BaseModel):
    prompt: str
    user_id: Optional[str] = "default_user"
    session_id: Optional[str] = None


class A2ARequest(BaseModel):
    jsonrpc: Optional[str] = "2.0"
    method: Optional[str] = "a2a.execute"
    params: Dict[str, Any]
    id: Optional[Any] = 1


@app.get("/")
def read_root():
    return {
        "service": "IT Helpdesk AI Assistant",
        "status": "online",
        "a2a_endpoint": "/a2a/app"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy", "model": root_agent.model_name}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    """Direct chat endpoint for user interactions."""
    try:
        result = root_agent.run(
            prompt=request.prompt,
            user_id=request.user_id,
            session_id=request.session_id
        )
        return result
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/a2a/app")
def a2a_rpc_endpoint(req: A2ARequest):
    """Agent-to-Agent (A2A) Protocol JSON-RPC Endpoint."""
    logger.info(f"Received A2A RPC request method '{req.method}' with params: {req.params}")
    
    prompt = req.params.get("prompt") or req.params.get("message") or ""
    user_id = req.params.get("user_id", "a2a_caller")
    session_id = req.params.get("session_id")

    if not prompt:
        return {
            "jsonrpc": "2.0",
            "error": {"code": -32602, "message": "Invalid params: 'prompt' or 'message' is required."},
            "id": req.id
        }

    agent_result = root_agent.run(prompt=prompt, user_id=user_id, session_id=session_id)

    return {
        "jsonrpc": "2.0",
        "result": {
            "response": agent_result["response"],
            "tool_calls": agent_result["tool_calls"],
            "status": agent_result["status"]
        },
        "id": req.id
    }
