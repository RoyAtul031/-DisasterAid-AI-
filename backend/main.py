import os
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.database import (
    init_db,
    save_session_location,
    get_session_location,
    save_message,
    get_chat_history
)
from backend.agents import orchestrate_disaster_aid
from backend.tools import get_emergency_contacts

# Configure logger
logger = logging.getLogger("disasteraid.main")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI, initializes the database on start."""
    logger.info("Initializing database...")
    await init_db()
    yield
    logger.info("Shutdown...")

app = FastAPI(
    title="DisasterAid AI API",
    description="Multi-agent emergency response system API",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    location: Optional[str] = None

class LocationRequest(BaseModel):
    session_id: str
    location: str

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """Processes a user emergency message and routes it to the agent system."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
        
    session_id = req.session_id or str(uuid.uuid4())
    
    # Determine location: request body -> db -> default
    location = req.location
    if not location or not location.strip():
        location = await get_session_location(session_id)
    if not location or not location.strip():
        location = "West Bengal, India"  # Default fallback
        
    # Save the user's message
    await save_message(session_id, "user", req.message)
    
    try:
        # Run agent orchestration
        result = await orchestrate_disaster_aid(req.message, location)
        
        # Save assistant response
        await save_message(
            session_id, 
            "assistant", 
            result["response"], 
            severity=result["severity"]
        )
        
        return {
            "session_id": session_id,
            "severity": result["severity"],
            "language": result["language"],
            "response": result["response"],
            "location": location
        }
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent coordination failed: {str(e)}")

@app.post("/api/location")
async def set_location(req: LocationRequest):
    """Updates the location for a session."""
    if not req.session_id or not req.location.strip():
        raise HTTPException(status_code=400, detail="session_id and location are required")
    await save_session_location(req.session_id, req.location)
    return {"status": "success", "message": f"Location updated to {req.location}"}

@app.get("/api/history")
async def chat_history(session_id: str):
    """Returns the chat history for a session."""
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id query parameter is required")
    history = await get_chat_history(session_id)
    return {"session_id": session_id, "history": history}

@app.get("/api/contacts")
async def contacts_endpoint(location: str):
    """Returns emergency contacts for a location."""
    if not location:
        raise HTTPException(status_code=400, detail="location query parameter is required")
    contacts = get_emergency_contacts(location)
    return contacts

# Serve Frontend Static Files
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logger.info(f"Mounted static files from {frontend_dir}")
else:
    logger.warning(f"Frontend directory '{frontend_dir}' does not exist yet. Static files not mounted.")
