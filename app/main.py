from fastapi import FastAPI

from app.api.routes import router_v1


app = FastAPI(title="Сервис работы с платежами по заказу", docs_url='/')

app.include_router(router_v1)

@app.get("/ping", tags=["health"])
async def health():
    return "pong"

