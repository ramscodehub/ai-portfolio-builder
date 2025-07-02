# backend/app/main.py
import sys
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import the new modules
from app.api import endpoints
from app.core import config
from app.services import llm_service

# Create the FastAPI app instance
app = FastAPI(
    title=config.GCP_PROJECT_ID,
    version="1.0.0",
    description="A web app to clone websites using AI"
)

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the static files directory for generated clones
app.mount(
    config.STATIC_CLONES_PATH_PREFIX,
    StaticFiles(directory=config.GENERATED_HTML_DIR_PATH),
    name="cloned_files"
)

# Include the API router
app.include_router(endpoints.router)

# Define startup event
@app.on_event("startup")
async def startup_event():
    print("Application startup: Attempting to initialize Vertex AI...")
    llm_service.initialize_vertex_ai()
    print("Startup complete.")

# Define a simple root endpoint for health checks
@app.get("/", summary="Health Check")
async def health_check():
    return {"status": "ok", "service": "Orchids Website Cloner API"}

# For running with `python -m app.main`
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
#uvicorn app.main:app --reload --port 8000