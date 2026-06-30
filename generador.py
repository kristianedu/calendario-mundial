import os
import requests
import pytz
from datetime import datetime, timedelta
from icalendar import Calendar
import re

API_KEY = os.environ.get("API_KEY")

from equipos import normalize_name

def actualizar_calendario():
    if not API_KEY:
        print("API_KEY no encontrada en las variables de entorno. Saliendo.")
        return

    now = datetime.now(pytz.utc)
    
    try:
        with open('base_mundial.ics', 'rb') as f:
            cal_data = f.read()
            cal = Calendar.from_ical(cal_data)
            cal_base = Calendar.from_ical(cal_data)
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
                    
                # Estimamos 4 horas máximo por si hay tiempos extra, penales largos o retrasos por VAR
                dtend_approx = dtstart + timedelta(hours=4)
                
                # Si estamos dentro de la ventana del partido
                if dtstart <= now <= dtend_approx:
                    summary = str(component.get('summary', ''))
                    if "(Final)" not in summary:
                        partido_activo = True
                        break
                    
    if not partido_activo:
        print("No hay partidos activos en este momento. Ahorrando peticiones a la API.")
        # Igual guardamos el calendario para que no falle el workflow de GitHub
        with open('mundial_2026_dinamico.ics', 'wb') as f:
            f.write(cal.to_ical())
        return
        
    # Si hay partido activo, consultamos la API
    print("¡Partido activo detectado! Consultando API de Football-Data.org...")
    
    # Ampliamos el rango a ayer y mañana para evitar problemas de husos horarios en la API
    date_from_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    date_to_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    headers = {
        'X-Auth-Token': API_KEY
    }
    
    url = f"https://api.football-data.org/v4/matches?competitions=WC&dateFrom={date_from_str}&dateTo={date_to_str}"
    
    try:
        response = requests.get(url, headers=headers)
        data = response.json()
        fixtures = data.get('matches', [])
    except Exception as e:
        print("Error consultando API:", e)
        return
    # Verificar errores de la API
    message = data.get('message', '')
    if 'restricted' in message.lower() or response.status_code != 200:
        print(f"  ❌ Error de la API: {message} (Código {response.status_code})")
        print("  ⚠️ Abortando actualización.")
        with open('mundial_2026_dinamico.ics', 'wb') as f:
            f.write(cal.to_ical())
        return
    
    print(f"  📊 {len(fixtures)} partidos encontrados en el rango de fechas.")
        
    # Crear un diccionario con los partidos
    resultados_api = {}
    fixture_ids = {}  # match_key → fixture_id para consultar eventos después
    for fix in fixtures:
        home = normalize_name(fix['homeTeam']['name'])
        away = normalize_name(fix['awayTeam']['name'])
        status = fix['status']
        
        # En Football-Data, el score actual generalmente está en fullTime si el partido terminó, o halfTime, etc.
        # En vivo, fullTime suele tener el score actual.
        score_info = fix.get('score', {})
        full_time = score_info.get('fullTime', {}) or {}
        home_goals = full_time.get('home')
        away_goals = full_time.get('away')
        fixture_id = fix['id']
        
        match_key = f"{home} vs {away}"
        resultados_api[match_key] = {
            'status': status,
            'home_goals': home_goals,
            'away_goals': away_goals,
            'home_name': home,
            'away_name': away
        }
        
        # Solo guardamos el fixture_id para partidos activos (en curso o finalizados hoy)
        if status in ['IN_PLAY', 'PAUSED', 'EXTRA_TIME', 'PENALTY_SHOOTOUT', 'FINISHED']:
            fixture_ids[match_key] = fixture_id
            
    # Consultar eventos (goles, tarjetas) de cada partido activo
    eventos_partido = {}  # match_key → texto formateado de eventos
    for match_key, fid in fixture_ids.items():
        try:
            # En v4, no hay endpoint /events pero vienen dentro del endpoint /matches/{id}
            events_url = f"https://api.football-data.org/v4/matches/{fid}"
            events_response = requests.get(events_url, headers=headers)
            events_data = events_response.json()
            
            events_list = events_data.get('goals', []) + events_data.get('bookings', []) + events_data.get('substitutions', [])
            
            # También en v4 la estructura podría variar o no dar eventos en el tier gratis, 
            # pero hacemos el esfuerzo por si los mandan en el endpoint del partido.
            # Según doc oficial, goals y bookings vienen dentro del object match en tier pagados.
            
            goles = []
            tarjetas = []
            
            for ev in events_list:
                # Determinar si es gol o tarjeta según sus llaves
                if 'scorer' in ev:  # Es un gol
                    jugador = ev.get('scorer', {}).get('name', 'Desconocido')
                    tiempo = ev.get('minute', '')
                    min_str = f"{tiempo}'"
                    tipo = ev.get('type', '')
                    if tipo == 'OWN':
                        goles.append(f"⚽🔴 {jugador} {min_str} (Autogol)")
                    elif tipo == 'PENALTY':
                        goles.append(f"⚽🅿️ {jugador} {min_str} (Penal)")
                    else:
                        goles.append(f"⚽ {jugador} {min_str}")
                elif 'player' in ev and 'card' in ev:  # Es una tarjeta
                    jugador = ev.get('player', {}).get('name', 'Desconocido')
                    tiempo = ev.get('minute', '')
                    min_str = f"{tiempo}'"
                    card_type = ev.get('card', '')
                    if card_type == 'YELLOW':
                        tarjetas.append(f"🟨 {jugador} {min_str}")
                    elif card_type == 'RED':
                        tarjetas.append(f"🟥 {jugador} {min_str}")
            
            # Construir texto de descripción
            lineas = []
            if goles:
                lineas.append("⚽ GOLES:")
                lineas.extend(goles)
            if tarjetas:
                if goles:
                    lineas.append("")  # Línea en blanco de separación
                lineas.append("📋 TARJETAS:")
                lineas.extend(tarjetas)
            
            if lineas:
                eventos_partido[match_key] = "\n".join(lineas)
                print(f"  📋 Eventos de {match_key}: {len(goles)} gol(es), {len(tarjetas)} tarjeta(s)")
            else:
                print(f"  📋 {match_key}: sin eventos aún")
                
        except Exception as e:
            print(f"  ⚠️ Error obteniendo eventos de {match_key}: {e}")
    
    # Procesar calendario
    modificados = 0
    hubo_finalizados = False
    
    for comp_dinamico, comp_base in zip(cal.walk(), cal_base.walk()):
        if comp_dinamico.name == "VEVENT":
            summary = str(comp_dinamico.get('summary'))
            
            for match_key, res in resultados_api.items():
                if res['home_name'] in summary and res['away_name'] in summary:
                    home_goals = res['home_goals'] if res['home_goals'] is not None else 0
                    away_goals = res['away_goals'] if res['away_goals'] is not None else 0

                    # Orientar los goles al orden en que aparecen los equipos en
                    # el summary (puede diferir del orden home/away de la API,
                    # p.ej. en los cruces KO que se arman en el orden del cuadro).
                    i_home = summary.find(res['home_name'])
                    i_away = summary.find(res['away_name'])
                    if i_away != -1 and i_home != -1 and i_away < i_home:
                        g1, g2 = away_goals, home_goals
                    else:
                        g1, g2 = home_goals, away_goals
                    resultado_str = f" [{g1}] - [{g2}] "

                    if " vs " in summary:
                        nuevo_summary = summary.replace(" vs ", resultado_str)
                    else:
                        nuevo_summary = re.sub(r" \[\d+\] - \[\d+\] ", resultado_str, summary)
                        
                    # Limpiar cualquier estado anterior entre paréntesis
                    nuevo_summary = re.sub(r" \([^)]*\)$", "", nuevo_summary)
                    
                    status = res['status']
                    
                    if status == "FINISHED":
                        nuevo_summary = nuevo_summary.replace("⚽", "✅").replace("🏆", "✅")
                        nuevo_summary += " (Final)"
                    elif status == "PAUSED":
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        nuevo_summary += " (Medio Tiempo)"
                    elif status == "EXTRA_TIME":
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        nuevo_summary += " (Tiempo Extra)"
                    elif status == "PENALTY_SHOOTOUT":
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        nuevo_summary += " (Penales)"
                    elif status == "IN_PLAY":
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        nuevo_summary += " (En Vivo)"
                            
                    comp_dinamico['summary'] = nuevo_summary
                    
                    # Inyectar eventos (goles/tarjetas) en la DESCRIPTION
                    if match_key in eventos_partido:
                        desc_existente = str(comp_dinamico.get('description', ''))
                        # Limpiar descripción de eventos anterior si existe
                        # Eliminar todo desde el separador "---" en adelante (goles y/o tarjetas)
                        desc_existente = re.sub(
                            r'\n?---\n(?:⚽ GOLES:|📋 TARJETAS:).*',
                            '',
                            desc_existente,
                            flags=re.DOTALL
                        )
                        nueva_desc = desc_existente.strip()
                        if nueva_desc:
                            nueva_desc += "\n---\n"
                        nueva_desc += eventos_partido[match_key]
                        comp_dinamico['description'] = nueva_desc
                        
                    # Guardado permanente en base_mundial.ics si el partido finalizó
                    if status == "FINISHED":
                        comp_base['summary'] = comp_dinamico.get('summary', '')
                        if 'description' in comp_dinamico:
                            comp_base['description'] = comp_dinamico.get('description', '')
                        hubo_finalizados = True
                    
                    modificados += 1
                    break
                    
    print(f"Calendario actualizado con {modificados} partidos en vivo.")
    with open('mundial_2026_dinamico.ics', 'wb') as f:
        f.write(cal.to_ical())
        
    if hubo_finalizados:
        print("Se detectaron partidos finalizados. Guardando marcadores permanentes en base_mundial.ics...")
        with open('base_mundial.ics', 'wb') as f:
            f.write(cal_base.to_ical())
        
if __name__ == "__main__":
    actualizar_calendario()
