import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

class FunctionCall(BaseModel):
    name: str
    arguments: dict

def obtener_post_y_miniatura(url: str) -> dict:
    # ... (tu lógica de scraping tal como la tenías) ...
    # devuelve {"texto": "...", "imagen_url": "..."} o {"texto": "", "imagen_url": "", "error": "..."}
    # (código igual al que ya tienes)

@app.post("/invoke_function")
async def invoke_function(call: FunctionCall):
    if call.name != "obtener_post_y_miniatura":
        raise HTTPException(status_code=400, detail="Función no soportada")
    args = call.arguments
    url = args.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Falta el parámetro 'url'")
    resultado = obtener_post_y_miniatura(url)
    return resultado

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
