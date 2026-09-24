from fastapi import FastAPI
from mangum import Mangum

app = FastAPI()


@app.get("/api/health")
def health():
    return {"status": "ok"}


handler = Mangum(app, lifespan="off")
