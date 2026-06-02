"""
actualizar_clasificados.py
Se ejecuta 1 vez al día (medianoche).
Consulta la API para ver si ya hay equipos asignados a los partidos
de las fases eliminatorias y actualiza base_mundial.ics con los nombres reales.
"""
import os
import requests
import re
from datetime import datetime
from icalendar import Calendar
from equipos import normalize_name, get_bandera

API_KEY = os.environ.get("API_KEY")

# Rondas eliminatorias que nos interesan
RONDAS_ELIMINATORIAS = [
    "Round of 32",
    "Round of 16",
    "Quarter-finals",
    "Semi-finals",
    "3rd Place",
    "Final"
]

# Mapa de nombre de ronda (API) → nombre en español para el SUMMARY
RONDAS_ESPANOL = {
    "Round of 32": "Treintaidosavos de Final",
    "Round of 16": "Octavos de Final",
    "Quarter-finals": "Cuartos de Final",
    "Semi-finals": "Semifinal",
    "3rd Place": "Partido por el Tercer Lugar",
    "Final": "GRAN FINAL"
}

def actualizar_clasificados():
    if not API_KEY:
        print("API_KEY no encontrada. Saliendo.")
        return False
    
    # 1. Consultar la API para obtener TODOS los partidos del Mundial
    headers = {'x-apisports-key': API_KEY}
    url = "https://v3.football.api-sports.io/fixtures?league=1&season=2026"
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        fixtures = data.get('response', [])
        print(f"API respondió con {len(fixtures)} partidos del Mundial.")
    except Exception as e:
        print(f"Error consultando API: {e}")
        return False
    
    if not fixtures:
        print("No se encontraron partidos del Mundial en la API todavía.")
        return False
    
    # 2. Filtrar solo los partidos de fases eliminatorias que YA tienen equipos asignados
    eliminatorias_api = {}
    for fix in fixtures:
        ronda = fix.get('league', {}).get('round', '')
        
        # Verificar si es una ronda eliminatoria
        es_eliminatoria = False
        for ronda_key in RONDAS_ELIMINATORIAS:
            if ronda_key.lower() in ronda.lower():
                es_eliminatoria = True
                break
        
        if not es_eliminatoria:
            continue
        
        home_name = fix['teams']['home']['name']
        away_name = fix['teams']['away']['name']
        
        # Si la API aún no tiene equipos asignados, los nombres serán None o "TBD"
        if not home_name or not away_name or home_name == "TBD" or away_name == "TBD":
            continue
        
        # Extraer fecha y hora UTC del partido
        fecha_utc = fix['fixture']['date']  # Formato ISO: "2026-06-28T17:00:00+00:00"
        dt = datetime.fromisoformat(fecha_utc)
        
        home_esp = normalize_name(home_name)
        away_esp = normalize_name(away_name)
        home_bandera = get_bandera(home_esp)
        away_bandera = get_bandera(away_esp)
        
        # Guardar por fecha+hora como clave única
        clave = dt.strftime("%Y%m%dT%H%M")
        eliminatorias_api[clave] = {
            'home': home_esp,
            'away': away_esp,
            'home_bandera': home_bandera,
            'away_bandera': away_bandera,
            'ronda': ronda,
            'venue': fix['fixture'].get('venue', {}).get('name', ''),
            'city': fix['fixture'].get('venue', {}).get('city', '')
        }
    
    print(f"Encontrados {len(eliminatorias_api)} partidos eliminatorios con equipos asignados.")
    
    if not eliminatorias_api:
        print("Ningún partido eliminatorio tiene equipos asignados aún.")
        return False
    
    # 3. Leer el archivo base del calendario
    try:
        with open('base_mundial.ics', 'rb') as f:
            cal = Calendar.from_ical(f.read())
    except FileNotFoundError:
        print("Archivo base_mundial.ics no encontrado.")
        return False
    
    # 4. Buscar los eventos genéricos de eliminatorias y reemplazarlos
    modificados = 0
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        
        uid = str(component.get('uid', ''))
        summary = str(component.get('summary', ''))
        
        # Solo nos interesan los eventos de fase eliminatoria (UIDs que empiezan con wc2026-KO)
        if not uid.startswith('wc2026-KO'):
            continue
        
        # Verificar si ya tiene equipos asignados (si ya tiene "vs" es que ya fue actualizado)
        if ' vs ' in summary:
            continue
        
        # Obtener la fecha/hora del evento para emparejar con la API
        dtstart = component.get('dtstart').dt
        if hasattr(dtstart, 'strftime'):
            # Convertir a UTC para comparar
            if hasattr(dtstart, 'tzinfo') and dtstart.tzinfo is not None:
                import pytz
                dtstart_utc = dtstart.astimezone(pytz.utc)
            else:
                dtstart_utc = dtstart
            
            clave_evento = dtstart_utc.strftime("%Y%m%dT%H%M")
            
            if clave_evento in eliminatorias_api:
                partido = eliminatorias_api[clave_evento]
                
                # Determinar el emoji y la ronda en español
                ronda_esp = ""
                for ronda_key, ronda_val in RONDAS_ESPANOL.items():
                    if ronda_key.lower() in partido['ronda'].lower():
                        ronda_esp = ronda_val
                        break
                
                # Construir el nuevo SUMMARY con banderas y nombres
                if "GRAN FINAL" in summary:
                    nuevo_summary = f"🏆🥇 {partido['home_bandera']} {partido['home']} vs {partido['away']} {partido['away_bandera']} - GRAN FINAL"
                elif "Tercer Lugar" in summary:
                    nuevo_summary = f"🏆🥉 {partido['home_bandera']} {partido['home']} vs {partido['away']} {partido['away_bandera']} - Tercer Lugar"
                elif "Semifinal" in summary:
                    nuevo_summary = f"🏆⭐ {partido['home_bandera']} {partido['home']} vs {partido['away']} {partido['away_bandera']} - {ronda_esp}"
                else:
                    nuevo_summary = f"🏆 {partido['home_bandera']} {partido['home']} vs {partido['away']} {partido['away_bandera']} - {ronda_esp}"
                
                component['summary'] = nuevo_summary
                
                # Actualizar ubicación si la API la tiene
                if partido['venue']:
                    location = partido['venue']
                    if partido['city']:
                        location += f", {partido['city']}"
                    component['location'] = location
                
                modificados += 1
                print(f"  ✅ Actualizado: {summary} → {nuevo_summary}")
    
    if modificados == 0:
        print("No se encontraron nuevos cruces para actualizar.")
        return False
    
    # 5. Guardar el archivo base actualizado
    with open('base_mundial.ics', 'wb') as f:
        f.write(cal.to_ical())
    
    print(f"\n🎉 ¡{modificados} partidos eliminatorios actualizados con equipos reales!")
    return True

if __name__ == "__main__":
    actualizar_clasificados()
