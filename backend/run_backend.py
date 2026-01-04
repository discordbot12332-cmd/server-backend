"""
Enhanced backend service that replaces Discord bot functionality
Provides CLI and can be packaged as standalone executable
"""

import asyncio
import subprocess
import sys
import os

# Add the current directory and api subdirectory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'api'))

def run_fastapi_server():
    """Run the FastAPI server"""
    import uvicorn
    from api.server import app
    
    print("🚀 Starting RAT Dashboard API Server...")
    print("📡 Server running at http://127.0.0.1:8000")
    print("📚 API Documentation at http://127.0.0.1:8000/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

def run_with_uvicorn():
    """Alternative way to run server using subprocess"""
    import uvicorn
    from api.server import app
    uvicorn.run(app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    try:
        run_fastapi_server()
    except KeyboardInterrupt:
        print("\n✋ Server stopped")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
