import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class FunctionCall(BaseModel):
    name: str
    arguments: dict


def obtener_post_y_miniatura(url: str) -> dict:
    """
    Hace GET a `url`, parsea con BeautifulSoup y devuelve:
      {
        "texto": "...",
        "imagen_url": "https://.../archivo.png"
      }
    O, si falla, un dict con 'texto' vacío e 'imagen_url' vacío + 'error'.
    """
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        return {"texto": "", "imagen_url": "", "error": f"No se pudo descargar la página: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")

    # 1) Buscar la primera tarjeta de post:
    tarjeta = soup.select_one("div.eael-grid-post-holder-inner")
    if not tarjeta:
        return {"texto": "", "imagen_url": "", "error": "No se encontró tarjeta de post."}

    # 2) Extraer URL de la imagen destacada:
    img_el = tarjeta.select_one("img.entered.lazyloaded") or tarjeta.select_one("img")
    imagen_url = ""
    if img_el:
        imagen_url = img_el.get("data-lazy-src") or img_el.get("src") or ""
        if not imagen_url:
            srcset = img_el.get("data-lazy-srcset") or img_el.get("srcset") or ""
            if srcset:
                partes = [p.strip().split()[0] for p in srcset.split(",") if p.strip()]
                if partes and partes[-1].startswith("http"):
                    imagen_url = partes[-1]

    # 3) Extraer enlace al post:
    enlace_el = tarjeta.select_one("a.eael-grid-post-link") or tarjeta.select_one("h2.entry-title a")
    if not enlace_el or not enlace_el.has_attr("href"):
        return {"texto": "", "imagen_url": imagen_url, "error": "No se pudo extraer enlace al post."}
    post_url = enlace_el["href"]

    # 4) Descargar el post y extraer todo el texto:
    texto = ""
    try:
        resp2 = requests.get(post_url, headers={"User-Agent": "Mozilla/5.0"})
        resp2.raise_for_status()
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        cont_elem = soup2.select_one("div.elementor-widget-container")
        if cont_elem:
            bloques = cont_elem.select("p, h2, h3")
            texto = " ".join([b.get_text(strip=True) for b in bloques if b.get_text(strip=True)])
        else:
            art = soup2.select_one("article")
            if art:
                parrafos = art.select("p")
                texto = " ".join([p.get_text(strip=True) for p in parrafos if p.get_text(strip=True)])
    except Exception:
        texto = ""

    return {"texto": texto, "imagen_url": imagen_url}


@app.post("/invoke_function")
async def invoke_function(call: FunctionCall):
    """
    Recibe JSON:
    {
      "name": "obtener_post_y_miniatura",
      "arguments": { "url": "https://salesystems.es/blog" }
    }
    Retorna el dict que devuelve `obtener_post_y_miniatura`.
    """
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
