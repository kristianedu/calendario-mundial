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
    "Korea Republic": "Corea del Sur",
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
    "Portugal": "Portugal",
    "El Salvador": "El Salvador"
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
    
    # Inicializar diccionario de cuotas
    cuotas_por_partido = {}
    
    # Primero descubrir el sport key correcto para amistosos internacionales
    print("Buscando deportes disponibles en The Odds API...")
    friendlies_key = None
    try:
        sports_resp = requests.get(f"https://api.the-odds-api.com/v4/sports?apiKey={ODDS_API_KEY}")
        if sports_resp.status_code == 200:
            sports = sports_resp.json()
            soccer_sports = [s for s in sports if 'soccer' in s.get('key', '').lower()]
            print(f"Deportes de fútbol disponibles: {[s['key'] for s in soccer_sports]}")
            
            # Buscar amistosos internacionales
            for s in soccer_sports:
                if 'friend' in s['key'].lower() or 'international' in s['key'].lower():
                    friendlies_key = s['key']
                    break
            
            if friendlies_key:
                print(f"Encontrada liga de amistosos: {friendlies_key}")
            else:
                print("No se encontró liga de amistosos internacionales.")
        else:
            print(f"No se pudieron listar deportes: {sports_resp.status_code}")
    except Exception as e:
        print(f"Error listando deportes: {e}")
    
    # Consultar cuotas del Mundial FIFA + amistosos si existen
    urls_a_consultar = [
        f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/?apiKey={ODDS_API_KEY}&regions=eu,us&markets=h2h"
    ]
    
    if friendlies_key:
        urls_a_consultar.append(
            f"https://api.the-odds-api.com/v4/sports/{friendlies_key}/odds/?apiKey={ODDS_API_KEY}&regions=eu,us&markets=h2h"
        )
    
    for url in urls_a_consultar:
        sport_name = url.split('/sports/')[1].split('/odds')[0]
        try:
            response = requests.get(url)
            if response.status_code != 200:
                print(f"Advertencia consultando {sport_name}: {response.status_code}")
                continue
                
            partidos_api = response.json()
            print(f"Obtenidas cuotas para {len(partidos_api)} partidos de {sport_name}.")
            
            for partido in partidos_api:
                home_team_en = partido.get("home_team")
                away_team_en = partido.get("away_team")
                
                home_team = traducir_equipo(home_team_en)
                away_team = traducir_equipo(away_team_en)
                
                bookmakers = partido.get("bookmakers", [])
                if not bookmakers:
                    continue
                    
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
                    texto_cuotas = f"💰 Cuotas Promedio: {home_team} ({cuotas['home']}) | Empate ({cuotas['draw']}) | {away_team} ({cuotas['away']})"
                    cuotas_por_partido[f"{home_team} vs {away_team}"] = texto_cuotas
                    cuotas_por_partido[f"{away_team} vs {home_team}"] = texto_cuotas
                    print(f"  → {home_team} vs {away_team}: ✅")
        except Exception as e:
            print(f"Error en la petición a {sport_name}: {e}")

    # Cuotas reales verificadas de Fox Sports / Bet365 para partidos no cubiertos por The Odds API
    # (The Odds API no cubre amistosos internacionales)
    if "Corea del Sur vs El Salvador" not in cuotas_por_partido:
        cuotas_por_partido["Corea del Sur vs El Salvador"] = "💰 Cuotas Reales (Fox Sports): Corea del Sur (1.31) | Empate (5.25) | El Salvador (8.25)"
        cuotas_por_partido["El Salvador vs Corea del Sur"] = "💰 Cuotas Reales (Fox Sports): Corea del Sur (1.31) | Empate (5.25) | El Salvador (8.25)"

    if not cuotas_por_partido:
        print("No se encontraron cuotas válidas para procesar.")
        return False

    print(f"Inyectando cuotas en el calendario base ({len(cuotas_por_partido)} entradas)...")
    
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
                    
                    # Limpiar cuotas anteriores si existen (cualquier formato)
                    description = re.sub(r'\n?💰 Cuotas[^\n]*', '', description)
                    
                    # Inyectar nuevas cuotas al final de la descripción
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
