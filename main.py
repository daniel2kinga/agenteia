import os
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import ORJSONResponse
from pydantic import BaseModel

app = FastAPI()


class FunctionCall(BaseModel):
    name: str
    arguments: dict


def obtener_post_y_miniatura(url: str) -> dict:
    """
    1) Descarga la página principal (url).
    2) Localiza la primera tarjeta de post: <div class="eael-grid-post-holder-inner">.
    3) Intenta extraer la miniatura (imagen destacada) de esa tarjeta:
         • Primero: <img class="entered lazyloaded">
         • Si no existe, cualquier <img> dentro de la tarjeta.
         • Si aún no hay, lee el style="background-image: url('…')" de la tarjeta.
    4) Extrae el enlace al post y descarga el HTML del post:
         • Intenta todos los <p> dentro de div.elementor-widget-container.
         • Si no hay, todos los <p> dentro de div.entry-content.
         • Si tampoco hay, todos los <p> dentro de <article>.
    5) Si en 3) no encontró miniatura, abre el HTML del post y busca <meta property="og:image"> para el fallback.
    6) Devuelve {"texto": "...", "imagen_url": "..."} (si falla, texto="" o imagen_url="").
    """
    # 1) Descargar la página principal
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        return {"texto": "", "imagen_url": "", "error": f"No se pudo descargar la página principal: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")

    # 2) Localizar la primera "tarjeta" de post
    tarjeta = soup.select_one("div.eael-grid-post-holder-inner")
    if not tarjeta:
        return {"texto": "", "imagen_url": "", "error": "No se encontró <div class='eael-grid-post-holder-inner'>."}

    # 3) Intentar extraer la imagen destacada desde la tarjeta
    imagen_url = ""
    # 3.1) Primer intento: <img class="entered lazyloaded">
    img_el = tarjeta.select_one("img.entered.lazyloaded")
    if not img_el:
        # 3.2) Segundo intento: cualquier <img> dentro de la tarjeta
        img_el = tarjeta.select_one("img")
    if img_el:
        # Si existe <img>, priorizamos data-lazy-src → src → srcset
        imagen_url = img_el.get("data-lazy-src") or img_el.get("src") or ""
        if not imagen_url:
            srcset = img_el.get("data-lazy-srcset") or img_el.get("srcset") or ""
            if srcset:
                # Tomamos la última URL del srcset
                partes = [p.strip().split()[0] for p in srcset.split(",") if p.strip()]
                if partes and partes[-1].startswith("http"):
                    imagen_url = partes[-1]

    if not imagen_url:
        # 3.3) Tercer intento: ver si la tarjeta tiene style="background-image: url('...')"
        style = tarjeta.get("style") or ""
        # Buscamos pattern: background-image: url('...'); o background-image: url("...");
        if "background-image" in style:
            # Ejemplo: style="background-image: url('https://example.com/imagen.png');"
            inicio = style.find("url(")
            if inicio != -1:
                # extraer entre url('  ') o url("  ")
                parte_url = style[inicio + 4 :].split(")")[0].strip().strip("'\"")
                if parte_url.startswith("http"):
                    imagen_url = parte_url

    # 4) Extraer el enlace al post
    enlace_el = tarjeta.select_one("a.eael-grid-post-link") or tarjeta.select_one("h2.entry-title a")
    if not enlace_el or not enlace_el.has_attr("href"):
        return {"texto": "", "imagen_url": imagen_url, "error": "No se pudo extraer enlace al post."}
    post_url = enlace_el["href"]

    # 5) Descargar el HTML del post y extraer texto
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
            # 5.2) Si no hay, todos los <p> dentro de div.entry-content
            parrafos = soup2.select("div.entry-content p")
            if parrafos:
                texto = " ".join([p.get_text(strip=True) for p in parrafos if p.get_text(strip=True)])
            else:
                # 5.3) Último recurso: todos los <p> dentro de <article>
                parrafos = soup2.select("article p")
                if parrafos:
                    texto = " ".join([p.get_text(strip=True) for p in parrafos if p.get_text(strip=True)])
                else:
                    texto = ""
    except Exception:
        texto = ""

    # 6) Si tras 3) la miniatura sigue vacía, buscamos <meta property="og:image">
    if not imagen_url:
        try:
            # Si no tenemos soup2 (porque falló la descarga del post), volvemos a descargarlo
            if 'soup2' not in locals():
                resp2 = requests.get(post_url, headers={"User-Agent": "Mozilla/5.0"})
                resp2.raise_for_status()
                soup2 = BeautifulSoup(resp2.text, "html.parser")
            meta_og = soup2.find("meta", property="og:image")
            if meta_og and meta_og.has_attr("content"):
                imagen_url = meta_og["content"]
        except Exception:
            pass

    return {"texto": texto, "imagen_url": imagen_url}


@app.get("/health")
def health_check():
    # Forzamos application/json con charset utf-8
    return ORJSONResponse({"status": "ok"}, media_type="application/json; charset=utf-8")


@app.post("/invoke_function")
async def invoke_function(call: FunctionCall):
    """
    Espera:
      {
        "name": "obtener_post_y_miniatura",
        "arguments": { "url": "https://salesystems.es/blog" }
      }
    Devuelve {"texto": "...", "imagen_url": "..."}.
    """
    if call.name != "obtener_post_y_miniatura":
        raise HTTPException(status_code=400, detail="Función no reconocida")

    args = call.arguments
    url = args.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Falta el parámetro 'url'")

    resultado = obtener_post_y_miniatura(url)
    return ORJSONResponse(resultado, media_type="application/json; charset=utf-8")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
