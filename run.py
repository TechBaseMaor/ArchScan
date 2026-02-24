"""Local run entrypoint — starts the ArchScan service on http://localhost:8000."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
