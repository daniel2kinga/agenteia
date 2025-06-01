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
    1) Hace GET a `url` (la página principal del blog).
    2) Localiza la primera tarjeta de post (<div class="eael-grid-post-holder-inner">).
    3) Extrae la URL de la imagen destacada de esa tarjeta.
    4) Extrae el enlace al post y hace GET a esa URL para capturar el texto completo.
       - Primero intenta todos los <p> dentro de `div.elementor-widget-container`.
       - Si no hay párrafos allí, intenta `div.entry-content p`.
       - Si tampoco hay, extrae todos los <p> dentro de `<article>`.
    5) Devuelve {"texto": "...", "imagen_url": "..."}.
    """
    # 1) Descargar la página principal
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        return {"texto": "", "imagen_url": "", "error": f"No se pudo descargar la página principal: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")

    # 2) Buscar la primera tarjeta de post (más reciente)
    tarjeta = soup.select_one("div.eael-grid-post-holder-inner")
    if not tarjeta:
        return {"texto": "", "imagen_url": "", "error": "No se encontró ninguna <div class='eael-grid-post-holder-inner'>."}

    # 3) Extraer la URL de la miniatura
    img_el = tarjeta.select_one("img.entered.lazyloaded") or tarjeta.select_one("img")
    imagen_url = ""
    if img_el:
        # Preferir data-lazy-src, luego src, luego srcset
        imagen_url = img_el.get("data-lazy-src") or img_el.get("src") or ""
        if not imagen_url:
            srcset = img_el.get("data-lazy-srcset") or img_el.get("srcset") or ""
            if srcset:
                partes = [p.strip().split()[0] for p in srcset.split(",") if p.strip()]
                if partes and partes[-1].startswith("http"):
                    imagen_url = partes[-1]

    # 4) Extraer enlace al post
    enlace_el = tarjeta.select_one("a.eael-grid-post-link") or tarjeta.select_one("h2.entry-title a")
    if not enlace_el or not enlace_el.has_attr("href"):
        return {"texto": "", "imagen_url": imagen_url, "error": "No se pudo extraer el enlace al post."}
    post_url = enlace_el["href"]

    # 5) Descargar el post y extraer texto
    texto = ""
    try:
        resp2 = requests.get(post_url, headers={"User-Agent": "Mozilla/5.0"})
        resp2.raise_for_status()
        soup2 = BeautifulSoup(resp2.text, "html.parser")

        # 5.1) Intentar todos los <p> dentro de div.elementor-widget-container
        parrafos = soup2.select("div.elementor-widget-container p")
        if parrafos:
            texto = " ".join([p.get_text(strip=True) for p in parrafos if p.get_text(strip=True)])
        else:
            # 5.2) Si no hay, probar todos los <p> dentro de div.entry-content
            parrafos = soup2.select("div.entry-content p")
            if parrafos:
                texto = " ".join([p.get_text(strip=True) for p in parrafos if p.get_text(strip=True)])
            else:
                # 5.3) Como último recurso, tomar todos los <p> dentro de <article>
                parrafos = soup2.select("article p")
                if parrafos:
                    texto = " ".join([p.get_text(strip=True) for p in parrafos if p.get_text(strip=True)])
                else:
                    texto = ""
    except Exception:
        texto = ""

    return {"texto": texto, "imagen_url": imagen_url}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/invoke_function")
async def invoke_function(call: FunctionCall):
    """
    Espera un JSON:
    {
      "name": "obtener_post_y_miniatura",
      "arguments": { "url": "https://salesystems.es/blog" }
    }
    Devuelve el resultado de la función de scraping.
    """
    if call.name != "obtener_post_y_miniatura":
        raise HTTPException(status_code=400, detail="Función no reconocida")

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
