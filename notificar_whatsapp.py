"""
notificar_whatsapp.py
Toma una captura de pantalla del bracket y la envía a un grupo de WhatsApp
via Green API, PERO solo cuando finaliza un partido (o se juega uno de grupo),
para no spamear el grupo.

Detección de cambios:
  Compara el bracket_data.json actual contra la versión ANTERIOR ya publicada
  (PREV_BRACKET_JSON, normalmente la copia que estaba en gh-pages antes de
  sobrescribirla). Notifica si:
    - un cruce de eliminatorias pasó a 'finished' (o cambió su marcador final), o
    - aumentó la cantidad de partidos jugados en algún grupo.
  Si no hay versión anterior (primer despliegue), solo establece la línea base
  sin enviar nada.

Variables de entorno:
  GREENAPI_ID         - ID de instancia de Green API
  GREENAPI_TOKEN      - Token de API de Green API
  WHATSAPP_GROUP_ID   - ID del grupo de WhatsApp (formato: XXXXXXXXXXX@g.us)
  PREV_BRACKET_JSON   - Ruta al bracket_data.json anterior (default: /tmp/old_bracket_data.json)
  BRACKET_HTML        - Página a capturar (default: bracket.html local)
  BRACKET_URL         - Fallback si no existe el HTML local (GitHub Pages)

Uso:
  python notificar_whatsapp.py             # Captura + envío (solo si hubo final)
  python notificar_whatsapp.py --dry-run   # Captura siempre, sin enviar (test)
"""
import os
import sys
import json
import asyncio
import functools
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

import requests

# Configuración
GREENAPI_ID = os.environ.get("GREENAPI_ID")
GREENAPI_TOKEN = os.environ.get("GREENAPI_TOKEN")
WHATSAPP_GROUP_ID = os.environ.get("WHATSAPP_GROUP_ID")
PREV_BRACKET_JSON = os.environ.get("PREV_BRACKET_JSON", "/tmp/old_bracket_data.json")
BRACKET_HTML = os.environ.get("BRACKET_HTML", "bracket.html")
BRACKET_URL = os.environ.get(
    "BRACKET_URL",
    "https://kristianedu.github.io/calendario-mundial/bracket.html"
)
BRACKET_JSON = "bracket_data.json"
SCREENSHOT_PATH = "bracket_screenshot.png"

RONDAS_LISTA = ["round_of_32", "round_of_16", "quarter_finals", "semi_finals"]
RONDAS_UNICAS = ["third_place", "final"]


# ─── Carga y detección de eventos ────────────────────────────────────
def cargar_json(path):
    """Carga un bracket_data.json; devuelve None si no existe o está vacío."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data or None
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _cruces_finalizados(data):
    """{id: partido} de los cruces de eliminatorias en estado 'finished'."""
    res = {}
    rounds = (data or {}).get("rounds", {}) or {}
    for key in RONDAS_LISTA:
        for p in rounds.get(key) or []:
            if p.get("status") == "finished":
                res[p["id"]] = p
    for key in RONDAS_UNICAS:
        p = rounds.get(key)
        if p and p.get("status") == "finished":
            res[p["id"]] = p
    return res


def _firma_cruce(p):
    """Firma del resultado de un cruce (para detectar marcadores corregidos)."""
    return (
        p["team1"].get("fullName"), p["team1"].get("score"),
        p["team2"].get("score"), p["team2"].get("fullName"),
    )


def _grupos_jugados(data):
    """{grupo: (jugados, total)} de cada grupo."""
    return {
        L: (info.get("played", 0), info.get("total", 0))
        for L, info in ((data or {}).get("groups") or {}).items()
    }


def _fmt_cruce(p):
    t1, t2 = p["team1"], p["team2"]
    return (f"✅ {t1.get('flag', '')} {t1.get('fullName')} "
            f"{t1.get('score')}-{t2.get('score')} "
            f"{t2.get('fullName')} {t2.get('flag', '')}".strip())


def detectar_eventos(viejo, nuevo):
    """Lista de líneas describiendo los partidos que finalizaron desde 'viejo'."""
    eventos = []

    viejo_ko = _cruces_finalizados(viejo)
    for mid, p in _cruces_finalizados(nuevo).items():
        prev = viejo_ko.get(mid)
        if prev and _firma_cruce(prev) == _firma_cruce(p):
            continue  # ya estaba finalizado con el mismo marcador
        eventos.append(_fmt_cruce(p))

    viejo_g = _grupos_jugados(viejo)
    for L, (jugados, total) in sorted(_grupos_jugados(nuevo).items()):
        prev_jugados = viejo_g.get(L, (0, 0))[0]
        if jugados > prev_jugados:
            eventos.append(f"⚽ Grupo {L}: {jugados}/{total} partidos jugados")

    return eventos


def construir_caption(data, eventos):
    caption = "🏆 Bracket del Mundial 2026 actualizado"
    if eventos:
        caption += "\n\n" + "\n".join(eventos)

    finalizados = len(_cruces_finalizados(data))
    total = 0
    rounds = data.get("rounds", {})
    for key in RONDAS_LISTA:
        total += len(rounds.get(key) or [])
    for key in RONDAS_UNICAS:
        if rounds.get(key):
            total += 1
    caption += f"\n\n📊 {finalizados}/{total} cruces de eliminatorias jugados"

    if data.get("champion"):
        c = data["champion"]
        caption += f"\n🥇 ¡Campeón: {c.get('flag', '')} {c.get('fullName')}!"
    return caption


# ─── Screenshot ──────────────────────────────────────────────────────
def _servir_local(directorio):
    """Levanta un http.server en un hilo sirviendo 'directorio'. Devuelve (httpd, port)."""
    handler = functools.partial(SimpleHTTPRequestHandler, directory=directorio)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


async def _capturar(url):
    from playwright.async_api import async_playwright
    print(f"  📸 Capturando: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)  # animaciones CSS iniciales
        await page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        await browser.close()
    kb = os.path.getsize(SCREENSHOT_PATH) / 1024
    print(f"  ✅ Screenshot guardado: {SCREENSHOT_PATH} ({kb:.0f} KB)")


def tomar_screenshot():
    """Captura el bracket. Prefiere el HTML local (sirviéndolo en localhost);
    si no existe, usa la URL pública de GitHub Pages."""
    try:
        import playwright.async_api  # noqa: F401
    except ImportError:
        print("  ❌ Playwright no está instalado:")
        print("     pip install playwright && playwright install chromium")
        return False

    httpd = None
    try:
        if os.path.exists(BRACKET_HTML):
            directorio = os.path.dirname(os.path.abspath(BRACKET_HTML)) or "."
            httpd, port = _servir_local(directorio)
            url = f"http://127.0.0.1:{port}/{os.path.basename(BRACKET_HTML)}"
        else:
            url = BRACKET_URL
        asyncio.run(_capturar(url))
        return True
    except Exception as e:
        print(f"  ❌ Error capturando screenshot: {e}")
        return False
    finally:
        if httpd:
            httpd.shutdown()


# ─── Envío WhatsApp ──────────────────────────────────────────────────
def enviar_whatsapp(caption):
    if not GREENAPI_ID or not GREENAPI_TOKEN or not WHATSAPP_GROUP_ID:
        print("  ❌ Faltan variables de entorno de Green API "
              "(GREENAPI_ID / GREENAPI_TOKEN / WHATSAPP_GROUP_ID).")
        return False
    if not os.path.exists(SCREENSHOT_PATH):
        print(f"  ❌ Screenshot no encontrado: {SCREENSHOT_PATH}")
        return False

    url = f"https://api.green-api.com/waInstance{GREENAPI_ID}/sendFileByUpload/{GREENAPI_TOKEN}"
    print(f"  📤 Enviando al grupo {WHATSAPP_GROUP_ID}...")
    try:
        with open(SCREENSHOT_PATH, "rb") as f:
            response = requests.post(
                url,
                data={"chatId": WHATSAPP_GROUP_ID, "caption": caption},
                files={"file": ("bracket_mundial_2026.png", f, "image/png")},
                timeout=30,
            )
        if response.status_code == 200 and response.json().get("idMessage"):
            print(f"  ✅ Enviado (ID: {response.json()['idMessage']})")
            return True
        print(f"  ⚠️ Respuesta inesperada [{response.status_code}]: {response.text}")
        return False
    except Exception as e:
        print(f"  ❌ Error enviando a WhatsApp: {e}")
        return False


# ─── Main ────────────────────────────────────────────────────────────
def main():
    dry_run = "--dry-run" in sys.argv
    print("🏆 Notificador de Bracket por WhatsApp")
    print("=" * 45)

    nuevo = cargar_json(BRACKET_JSON)
    if nuevo is None:
        print(f"  ⚠️ {BRACKET_JSON} no encontrado. Nada que hacer.")
        return

    eventos = []
    if not dry_run:
        viejo = cargar_json(PREV_BRACKET_JSON)
        if viejo is None:
            print("  ℹ️ Sin versión anterior: se establece la línea base, "
                  "no se envía notificación.")
            return
        eventos = detectar_eventos(viejo, nuevo)
        if not eventos:
            print("  ℹ️ Ningún partido finalizó desde la última vez. No se envía.")
            return
        print(f"  🔔 {len(eventos)} evento(s) detectado(s):")
        for e in eventos:
            print(f"     • {e}")

    if not tomar_screenshot():
        return

    if dry_run:
        print("  ℹ️ Modo dry-run: screenshot tomado, no se envía a WhatsApp.")
    else:
        enviar_whatsapp(construir_caption(nuevo, eventos))

    print("=" * 45)
    print("✅ Proceso completado.")


if __name__ == "__main__":
    main()
