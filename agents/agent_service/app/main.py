from fastapi import FastAPI

app = FastAPI(title="Okala Generic Agent Service", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "agent"}