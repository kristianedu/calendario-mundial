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
    headers = {'X-Auth-Token': API_KEY}
    url = "https://api.football-data.org/v4/competitions/WC/matches"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        fixtures = data.get('matches', [])
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
        ronda = fix.get('stage', '')
        
        # Verificar si es una ronda eliminatoria. En football-data suelen usar nombres como LAST_16, QUARTER_FINALS, SEMI_FINALS, FINAL, THIRD_PLACE
        es_eliminatoria = False
        rondas_reales = ["LAST_32", "LAST_16", "QUARTER_FINALS", "SEMI_FINALS", "THIRD_PLACE", "FINAL"]
        if ronda in rondas_reales:
            es_eliminatoria = True
        
        if not es_eliminatoria:
            continue
        
        home_name = fix.get('homeTeam', {}).get('name')
        away_name = fix.get('awayTeam', {}).get('name')
        
        # Si la API aún no tiene equipos asignados, los nombres pueden no venir o ser vacíos
        if not home_name or not away_name or home_name == "TBD" or away_name == "TBD":
            continue
        
        # Extraer fecha y hora UTC del partido
        fecha_utc = fix.get('utcDate')  # Formato ISO: "2026-06-28T17:00:00Z"
        if not fecha_utc:
            continue
            
        dt = datetime.fromisoformat(fecha_utc.replace('Z', '+00:00'))
        
        home_esp = normalize_name(home_name)
        away_esp = normalize_name(away_name)
        home_bandera = get_bandera(home_esp)
        away_bandera = get_bandera(away_esp)
        
        # Guardar por fecha+hora como clave única
        clave = dt.strftime("%Y%m%dT%H%M")
        
        # Mapear nombre de ronda para buscar en el diccionario español
        ronda_map = {
            "LAST_32": "Round of 32",
            "LAST_16": "Round of 16",
            "QUARTER_FINALS": "Quarter-finals",
            "SEMI_FINALS": "Semi-finals",
            "THIRD_PLACE": "3rd Place",
            "FINAL": "Final"
        }
        ronda_api_nombre = ronda_map.get(ronda, ronda)
        
        eliminatorias_api[clave] = {
            'home': home_esp,
            'away': away_esp,
            'home_bandera': home_bandera,
            'away_bandera': away_bandera,
            'ronda': ronda_api_nombre,
            'venue': '', # En v4 de football-data el estadio puede no venir a nivel gratuito fácilmente
            'city': ''
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
    
    # 4. Asignar cada partido a su slot por EQUIPOS (no por fecha). Se proyecta
    #    quién juega en cada cruce desde la estructura oficial y se busca el
    #    partido de la API con esos dos equipos. Evita que se pierdan o se
    #    ubiquen mal (el bug del emparejamiento por hora). Si la proyección
    #    falla, cae al emparejamiento por fecha (lógica anterior).
    try:
        import generar_bracket
        proyeccion = generar_bracket.proyectar_equipos_ko(cal)
    except Exception as e:
        print(f"  ⚠️ No se pudo proyectar equipos ({e}); se usa fecha.")
        proyeccion = None

    fixtures_por_par = {frozenset({p['home'], p['away']}): p
                        for p in eliminatorias_api.values()}

    modificados = 0
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get('uid', ''))
        summary = str(component.get('summary', ''))
        m = re.search(r'wc2026-KO-(\d+)', uid)
        if not m:
            continue
        # Si ya tiene equipos ("vs") o marcador ("[x] - [y]"), no tocar.
        if ' vs ' in summary or '] - [' in summary:
            continue
        ko_num = int(m.group(1))

        partido = orden = None
        if proyeccion is not None:
            n1, n2 = proyeccion.get(ko_num, (None, None))
            if n1 and n2:
                partido = fixtures_por_par.get(frozenset({n1, n2}))
                orden = (n1, n2)  # respeta la orientación del cuadro
        else:
            dtstart = component.get('dtstart').dt
            if hasattr(dtstart, 'strftime'):
                if getattr(dtstart, 'tzinfo', None) is not None:
                    import pytz
                    dtstart = dtstart.astimezone(pytz.utc)
                partido = eliminatorias_api.get(dtstart.strftime("%Y%m%dT%H%M"))
                if partido:
                    orden = (partido['home'], partido['away'])

        if not partido or not orden:
            continue

        b1, b2 = get_bandera(orden[0]), get_bandera(orden[1])
        ronda_esp = ""
        for ronda_key, ronda_val in RONDAS_ESPANOL.items():
            if ronda_key.lower() in partido['ronda'].lower():
                ronda_esp = ronda_val
                break

        if "GRAN FINAL" in summary:
            nuevo_summary = f"🏆🥇 {b1} {orden[0]} vs {orden[1]} {b2} - GRAN FINAL"
        elif "Tercer Lugar" in summary:
            nuevo_summary = f"🏆🥉 {b1} {orden[0]} vs {orden[1]} {b2} - Tercer Lugar"
        elif "Semifinal" in summary:
            nuevo_summary = f"🏆⭐ {b1} {orden[0]} vs {orden[1]} {b2} - {ronda_esp}"
        else:
            nuevo_summary = f"🏆 {b1} {orden[0]} vs {orden[1]} {b2} - {ronda_esp}"

        component['summary'] = nuevo_summary
        if partido['venue']:
            location = partido['venue']
            if partido['city']:
                location += f", {partido['city']}"
            component['location'] = location

        modificados += 1
        print(f"  ✅ KO-{ko_num:03d}: {orden[0]} vs {orden[1]}")
    
    if modificados == 0:
        print("No se encontraron nuevos cruces para actualizar.")
        return False
    
    # 5. Guardar el archivo base actualizado
    if modificados > 0:
        with open('base_mundial.ics', 'wb') as f:
            f.write(cal.to_ical())
        print(f"\n🎉 ¡{modificados} partidos eliminatorios actualizados con equipos reales!")
    return modificados > 0

def actualizar_tablas():
    if not API_KEY:
        return False
        
    headers = {'X-Auth-Token': API_KEY}
    url = "https://api.football-data.org/v4/competitions/WC/standings"
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        data = response.json()
        standings_data = data.get('standings', [])
        if not standings_data:
            print("No se encontraron tablas de posiciones.")
            return False
            
    except Exception as e:
        print(f"Error consultando tablas: {e}")
        return False
        
    # Formatear tablas por grupo
    tablas_formateadas = {}
    for group_standings in standings_data:
        # standings_data es una lista donde cada item es un grupo si type=="TOTAL"
        if group_standings.get('type') != 'TOTAL':
            continue
            
        group_name = group_standings.get('group', '') # Ej: "GROUP_A"
        if not group_name:
            continue
            
        group_letter = group_name.split('_')[-1]
        table = group_standings.get('table', [])
        
        if not table:
            continue
            
        lineas = [f"📊 Tabla del Grupo {group_letter}:"]
        for team_data in table:
            rank = team_data.get('position')
            team_name = team_data.get('team', {}).get('name', '')
            points = team_data.get('points', 0)
            goals_diff = team_data.get('goalDifference', 0)
            
            team_esp = normalize_name(team_name)
            bandera = get_bandera(team_esp)
            
            # 1. 🇲🇽 México - 6 pts (GD: +2)
            gd_str = f"+{goals_diff}" if goals_diff > 0 else str(goals_diff)
            lineas.append(f"{rank}. {bandera} {team_esp} - {points} pts (DG: {gd_str})")
            
        tablas_formateadas[f"Grupo {group_letter}"] = "\n".join(lineas)
        
    print(f"Tablas formateadas para {len(tablas_formateadas)} grupos.")
    
    # Inyectar tablas en el archivo base_mundial.ics
    try:
        with open('base_mundial.ics', 'rb') as f:
            cal = Calendar.from_ical(f.read())
    except FileNotFoundError:
        return False
        
    modificados = 0
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
            
        description = str(component.get('description', ''))
        
        # Buscar "Grupo X" en la descripción
        match = re.search(r'(Grupo [A-L])', description)
        if match:
            grupo = match.group(1)
            if grupo in tablas_formateadas:
                # Limpiar tabla anterior si existe
                description = re.sub(r'\n+📊 Tabla del Grupo [A-L]:.*', '', description, flags=re.DOTALL)
                
                # Agregar tabla nueva
                nueva_desc = description.strip() + "\n\n" + tablas_formateadas[grupo]
                component['description'] = nueva_desc
                modificados += 1
                
    if modificados > 0:
        with open('base_mundial.ics', 'wb') as f:
            f.write(cal.to_ical())
        print(f"Tablas inyectadas en {modificados} partidos de fase de grupos.")
        return True
    return False

if __name__ == "__main__":
    cambios_clasificados = actualizar_clasificados()
    cambios_tablas = actualizar_tablas()
    
    # Si alguna de las dos funciones hizo cambios, el script es exitoso
    if cambios_clasificados or cambios_tablas:
        print("Finalizado con éxito.")
    else:
        print("Finalizado sin cambios.")
