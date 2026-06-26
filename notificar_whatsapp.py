"""
notificar_whatsapp.py
Toma una captura de pantalla del bracket publicado en GitHub Pages
y la envía a un grupo de WhatsApp via Green API.

Variables de entorno requeridas:
  GREENAPI_ID       - ID de instancia de Green API
  GREENAPI_TOKEN    - Token de API de Green API
  WHATSAPP_GROUP_ID - ID del grupo de WhatsApp (formato: XXXXXXXXXXX@g.us)
  BRACKET_URL       - URL del bracket (default: GitHub Pages)

Uso:
  python notificar_whatsapp.py             # Captura + envío
  python notificar_whatsapp.py --dry-run   # Solo captura, sin enviar
"""
import os
import sys
import json
import hashlib
import asyncio
import requests

# Configuración
GREENAPI_ID = os.environ.get("GREENAPI_ID")
GREENAPI_TOKEN = os.environ.get("GREENAPI_TOKEN")
WHATSAPP_GROUP_ID = os.environ.get("WHATSAPP_GROUP_ID")
BRACKET_URL = os.environ.get(
    "BRACKET_URL",
    "https://kristianedu.github.io/calendario-mundial/bracket.html"
)
SCREENSHOT_PATH = "bracket_screenshot.png"
HASH_FILE = ".bracket_hash"


def calcular_hash_bracket():
    """Calcula un hash del bracket_data.json para detectar cambios."""
    try:
        with open("bracket_data.json", "r") as f:
            data = f.read()
        return hashlib.md5(data.encode()).hexdigest()
    except FileNotFoundError:
        return None


def hubo_cambios():
    """Verifica si el bracket cambió respecto a la última notificación."""
    hash_actual = calcular_hash_bracket()
    if hash_actual is None:
        print("  ⚠️ bracket_data.json no encontrado. Saltando.")
        return False

    hash_anterior = None
    try:
        with open(HASH_FILE, "r") as f:
            hash_anterior = f.read().strip()
    except FileNotFoundError:
        pass

    if hash_actual == hash_anterior:
        print("  ℹ️ El bracket no ha cambiado. No se enviará notificación.")
        return False

    # Guardar nuevo hash
    with open(HASH_FILE, "w") as f:
        f.write(hash_actual)

    print(f"  🔄 Cambio detectado en el bracket (hash: {hash_actual[:8]}...)")
    return True


async def tomar_screenshot():
    """Toma una captura de pantalla del bracket usando Playwright."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("  ❌ Playwright no está instalado. Ejecuta:")
        print("     pip install playwright && playwright install chromium")
        return False

    print(f"  📸 Capturando screenshot de: {BRACKET_URL}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        await page.goto(BRACKET_URL, wait_until="networkidle", timeout=30000)

        # Esperar un momento extra para que las animaciones CSS iniciales terminen
        await page.wait_for_timeout(2000)

        # Capturar toda la página
        await page.screenshot(path=SCREENSHOT_PATH, full_page=True)

        await browser.close()

    file_size = os.path.getsize(SCREENSHOT_PATH)
    print(f"  ✅ Screenshot guardado: {SCREENSHOT_PATH} ({file_size / 1024:.0f} KB)")
    return True


def enviar_whatsapp():
    """Envía la captura de pantalla al grupo de WhatsApp via Green API."""
    if not GREENAPI_ID or not GREENAPI_TOKEN or not WHATSAPP_GROUP_ID:
        print("  ❌ Faltan variables de entorno de Green API:")
        if not GREENAPI_ID:
            print("     - GREENAPI_ID")
        if not GREENAPI_TOKEN:
            print("     - GREENAPI_TOKEN")
        if not WHATSAPP_GROUP_ID:
            print("     - WHATSAPP_GROUP_ID")
        return False

    if not os.path.exists(SCREENSHOT_PATH):
        print(f"  ❌ Screenshot no encontrado: {SCREENSHOT_PATH}")
        return False

    url = f"https://api.green-api.com/waInstance{GREENAPI_ID}/sendFileByUpload/{GREENAPI_TOKEN}"

    # Construir caption con info del bracket
    caption = "🏆 Bracket del Mundial 2026 actualizado"
    try:
        with open("bracket_data.json", "r") as f:
            data = json.load(f)
        finalizados = 0
        total = 0
        for ronda_key in ["round_of_32", "round_of_16", "quarter_finals", "semi_finals"]:
            partidos = data["rounds"].get(ronda_key, [])
            for p in partidos:
                total += 1
                if p["status"] == "finished":
                    finalizados += 1
        for ronda_key in ["third_place", "final"]:
            p = data["rounds"].get(ronda_key)
            if p:
                total += 1
                if p["status"] == "finished":
                    finalizados += 1

        caption += f"\n📊 {finalizados}/{total} partidos jugados"

        if data.get("champion"):
            caption += f"\n🥇 ¡Campeón: {data['champion']['flag']} {data['champion']['fullName']}!"
    except Exception:
        pass

    print(f"  📤 Enviando al grupo de WhatsApp...")
    print(f"     Grupo: {WHATSAPP_GROUP_ID}")

    try:
        with open(SCREENSHOT_PATH, "rb") as f:
            response = requests.post(
                url,
                data={
                    "chatId": WHATSAPP_GROUP_ID,
                    "caption": caption,
                },
                files={
                    "file": ("bracket_mundial_2026.png", f, "image/png")
                },
                timeout=30
            )

        if response.status_code == 200:
            result = response.json()
            if result.get("idMessage"):
                print(f"  ✅ Mensaje enviado exitosamente (ID: {result['idMessage']})")
                return True
            else:
                print(f"  ⚠️ Respuesta inesperada: {result}")
                return False
        else:
            print(f"  ❌ Error HTTP {response.status_code}: {response.text}")
            return False

    except Exception as e:
        print(f"  ❌ Error enviando a WhatsApp: {e}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv

    print("🏆 Notificador de Bracket por WhatsApp")
    print("=" * 45)

    # 1. Verificar si hubo cambios
    if not dry_run and not hubo_cambios():
        return

    # 2. Tomar screenshot
    success = asyncio.run(tomar_screenshot())
    if not success:
        return

    # 3. Enviar a WhatsApp (salvo dry-run)
    if dry_run:
        print("  ℹ️ Modo dry-run: screenshot tomado pero no se envió a WhatsApp.")
    else:
        enviar_whatsapp()

    print("=" * 45)
    print("✅ Proceso completado.")


if __name__ == "__main__":
    main()
