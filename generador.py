import os
import requests
import pytz
from datetime import datetime, timedelta
from icalendar import Calendar
import re

API_KEY = os.environ.get("API_KEY")

# Mapa de nombres de API (Inglés) a nombres en nuestro calendario (Español)
EQUIPOS_MAP = {
    "Mexico": "México",
    "South Africa": "Sudáfrica",
    "Canada": "Canadá",
    "Bosnia": "Bosnia y Herzegovina",
    "Spain": "España",
    "Germany": "Alemania",
    "Netherlands": "Países Bajos",
    "United States": "Estados Unidos",
    "South Korea": "Corea del Sur",
    "Czech Republic": "Chequia",
    "Switzerland": "Suiza",
    "Morocco": "Marruecos",
    "Japan": "Japón",
    "Ecuador": "Ecuador",
    "England": "Inglaterra",
    "France": "Francia",
    "Portugal": "Portugal"
}

def normalize_name(name):
    return EQUIPOS_MAP.get(name, name)

def actualizar_calendario():
    if not API_KEY:
        print("API_KEY no encontrada en las variables de entorno. Saliendo.")
        return

    now = datetime.now(pytz.utc)
    
    try:
        with open('base_mundial.ics', 'rb') as f:
            cal = Calendar.from_ical(f.read())
    except FileNotFoundError:
        print("Archivo base_mundial.ics no encontrado.")
        return
        
    # Verificar si hay algún partido activo (ventana de 3 horas desde el inicio)
    partido_activo = False
    for component in cal.walk():
        if component.name == "VEVENT":
            dtstart = component.get('dtstart').dt
            if type(dtstart) is datetime:
                # Asegurar timezone UTC
                if dtstart.tzinfo is None:
                    dtstart = dtstart.replace(tzinfo=pytz.utc)
                elif dtstart.tzinfo != pytz.utc:
                    dtstart = dtstart.astimezone(pytz.utc)
                    
                dtend_approx = dtstart + timedelta(hours=3)
                
                # Si estamos dentro de la ventana del partido
                if dtstart <= now <= dtend_approx:
                    partido_activo = True
                    break
                    
    if not partido_activo:
        print("No hay partidos activos en este momento. Ahorrando peticiones a la API.")
        # Igual guardamos el calendario para que no falle el workflow de GitHub
        with open('mundial_2026_dinamico.ics', 'wb') as f:
            f.write(cal.to_ical())
        return
        
    # Si hay partido activo, consultamos la API
    print("¡Partido activo detectado! Consultando API de API-Football...")
    date_str = now.strftime("%Y-%m-%d")
    
    headers = {
        'x-apisports-key': API_KEY
    }
    
    url = f"https://v3.football.api-sports.io/fixtures?date={date_str}"
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        fixtures = data.get('response', [])
    except Exception as e:
        print("Error consultando API:", e)
        return
        
    # Crear un diccionario con los partidos del Mundial (League ID 1)
    resultados_api = {}
    for fix in fixtures:
        league_id = fix.get('league', {}).get('id')
        if league_id == 1: # 1 es el ID del Mundial en API-Football
            home = normalize_name(fix['teams']['home']['name'])
            away = normalize_name(fix['teams']['away']['name'])
            status = fix['fixture']['status']['short']
            home_goals = fix['goals']['home']
            away_goals = fix['goals']['away']
            
            resultados_api[f"{home} vs {away}"] = {
                'status': status,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'home_name': home,
                'away_name': away
            }
            
    # Procesar calendario
    modificados = 0
    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get('summary'))
            
            for match_key, res in resultados_api.items():
                if res['home_name'] in summary and res['away_name'] in summary:
                    home_goals = res['home_goals'] if res['home_goals'] is not None else 0
                    away_goals = res['away_goals'] if res['away_goals'] is not None else 0
                    
                    resultado_str = f" [{home_goals}] - [{away_goals}] "
                    
                    if " vs " in summary:
                        nuevo_summary = summary.replace(" vs ", resultado_str)
                    else:
                        nuevo_summary = re.sub(r" \[\d+\] - \[\d+\] ", resultado_str, summary)
                        
                    status = res['status']
                    if status in ["FT", "AET", "PEN"]:
                        nuevo_summary = nuevo_summary.replace("⚽", "✅").replace("🏆", "✅")
                        if "(Final)" not in nuevo_summary:
                            nuevo_summary += " (Final)"
                    elif status in ["1H", "2H", "HT", "ET", "P"]:
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        if "(En Vivo)" not in nuevo_summary:
                            nuevo_summary += " (En Vivo)"
                            
                    component['summary'] = nuevo_summary
                    modificados += 1
                    break
                    
    print(f"Calendario actualizado con {modificados} partidos en vivo.")
    with open('mundial_2026_dinamico.ics', 'wb') as f:
        f.write(cal.to_ical())
        
if __name__ == "__main__":
    actualizar_calendario()
