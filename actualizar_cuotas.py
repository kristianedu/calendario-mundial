import os
import requests
import re
from icalendar import Calendar
from equipos import normalize_name

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")

# Diccionario para traducir nombres en inglés comunes de The Odds API a español
TRADUCCIONES = {
    "United States": "EE.UU.",
    "USA": "EE.UU.",
    "Mexico": "México",
    "Spain": "España",
    "Germany": "Alemania",
    "France": "Francia",
    "Italy": "Italia",
    "England": "Inglaterra",
    "Brazil": "Brasil",
    "South Africa": "Sudáfrica",
    "South Korea": "Corea del Sur",
    "Czech Republic": "Chequia",
    "Canada": "Canadá",
    "Morocco": "Marruecos",
    "Haiti": "Haití",
    "Turkey": "Turquía",
    "Japan": "Japón",
    "Netherlands": "Países Bajos",
    "Belgium": "Bélgica",
    "Croatia": "Croacia",
    "Switzerland": "Suiza",
    "Uruguay": "Uruguay",
    "Cameroon": "Camerún",
    "Senegal": "Senegal",
    "Portugal": "Portugal"
    # Se pueden ir agregando más según se necesite
}

def traducir_equipo(nombre_en):
    """Traduce del inglés al español y normaliza el nombre"""
    esp = TRADUCCIONES.get(nombre_en, nombre_en)
    return normalize_name(esp)

def actualizar_cuotas():
    if not ODDS_API_KEY:
        print("ODDS_API_KEY no encontrada en las variables de entorno. Saliendo.")
        return False
        
    print("Consultando The Odds API...")
    url = f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/?apiKey={ODDS_API_KEY}&regions=eu,us&markets=h2h"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error consultando Odds API: {response.status_code} - {response.text}")
            return False
            
        partidos_api = response.json()
        print(f"Obtenidas cuotas para {len(partidos_api)} partidos.")
    except Exception as e:
        print(f"Error en la petición: {e}")
        return False

    if not partidos_api:
        return False

    # Procesar cuotas por partido
    cuotas_por_partido = {}
    
    for partido in partidos_api:
        home_team_en = partido.get("home_team")
        away_team_en = partido.get("away_team")
        
        home_team = traducir_equipo(home_team_en)
        away_team = traducir_equipo(away_team_en)
        
        # Buscar la mejor casa de apuestas (ej. Bet365 o la primera disponible)
        bookmakers = partido.get("bookmakers", [])
        if not bookmakers:
            continue
            
        # Tomar la primera casa de apuestas (suelen estar ordenadas por relevancia/última actualización)
        mercados = bookmakers[0].get("markets", [])
        h2h_market = next((m for m in mercados if m["key"] == "h2h"), None)
        
        if not h2h_market:
            continue
            
        outcomes = h2h_market.get("outcomes", [])
        cuotas = {}
        for outcome in outcomes:
            name = outcome["name"]
            price = outcome["price"]
            
            if name == home_team_en:
                cuotas["home"] = price
            elif name == away_team_en:
                cuotas["away"] = price
            elif name == "Draw":
                cuotas["draw"] = price
                
        if "home" in cuotas and "away" in cuotas and "draw" in cuotas:
            # Generar string de cuotas
            # Ej: 💰 Cuotas: 🇲🇽 México (1.80) | Empate (3.50) | 🇿🇦 Sudáfrica (4.20)
            texto_cuotas = f"💰 Cuotas Promedio: {home_team} ({cuotas['home']}) | Empate ({cuotas['draw']}) | {away_team} ({cuotas['away']})"
            cuotas_por_partido[f"{home_team} vs {away_team}"] = texto_cuotas
            cuotas_por_partido[f"{away_team} vs {home_team}"] = texto_cuotas # Por si acaso están al revés en el ICS

    # === MOCK DATA PARA PRUEBAS EN VIVO ===
    # A petición tuya, inyectamos cuotas falsas a los partidos de hoy para ver cómo queda:
    cuotas_por_partido["CA Barracas Central vs Huracán"] = "💰 Cuotas Promedio: CA Barracas Central (2.10) | Empate (3.20) | Huracán (3.50)"
    cuotas_por_partido["Huracán vs CA Barracas Central"] = "💰 Cuotas Promedio: CA Barracas Central (2.10) | Empate (3.20) | Huracán (3.50)"
    cuotas_por_partido["Haití vs Nueva Zelanda"] = "💰 Cuotas Promedio: Haití (4.50) | Empate (3.80) | Nueva Zelanda (1.75)"
    cuotas_por_partido["Nueva Zelanda vs Haití"] = "💰 Cuotas Promedio: Haití (4.50) | Empate (3.80) | Nueva Zelanda (1.75)"
    # ======================================

    if not cuotas_por_partido:
        print("No se encontraron cuotas válidas para procesar.")
        return False

    print(f"Inyectando cuotas en el calendario base...")
    
    try:
        with open('base_mundial.ics', 'rb') as f:
            cal = Calendar.from_ical(f.read())
    except FileNotFoundError:
        print("Archivo base_mundial.ics no encontrado.")
        return False
        
    modificados = 0
    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get("summary", ""))
            
            # Buscar coincidencia
            for match_key, texto_cuotas in cuotas_por_partido.items():
                equipos = match_key.split(" vs ")
                if len(equipos) == 2 and equipos[0] in summary and equipos[1] in summary:
                    description = str(component.get("description", ""))
                    
                    # Limpiar cuotas anteriores si existen
                    description = re.sub(r'\n?💰 Cuotas Promedio:.*', '', description)
                    
                    # Inyectar nuevas cuotas al inicio de la descripción o justo después de la info base
                    # Lo pondremos al final de la descripción
                    nueva_desc = description.strip() + "\n\n" + texto_cuotas
                    component["description"] = nueva_desc
                    modificados += 1
                    break
                    
    if modificados > 0:
        with open('base_mundial.ics', 'wb') as f:
            f.write(cal.to_ical())
        print(f"🎉 Cuotas actualizadas en {modificados} partidos.")
        return True
    else:
        print("No se inyectaron cuotas (no coincidieron los nombres de los equipos).")
        return False

if __name__ == "__main__":
    actualizar_cuotas()
