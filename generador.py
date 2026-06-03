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
    fixture_ids = {}  # match_key → fixture_id para consultar eventos después
    for fix in fixtures:
        league_id = fix.get('league', {}).get('id')
        if True: # Aceptamos cualquier liga para ver el partido de Haití en vivo
            home = normalize_name(fix['teams']['home']['name'])
            away = normalize_name(fix['teams']['away']['name'])
            status = fix['fixture']['status']['short']
            elapsed = fix['fixture']['status'].get('elapsed')  # Minuto actual
            home_goals = fix['goals']['home']
            away_goals = fix['goals']['away']
            fixture_id = fix['fixture']['id']
            
            match_key = f"{home} vs {away}"
            resultados_api[match_key] = {
                'status': status,
                'elapsed': elapsed,
                'home_goals': home_goals,
                'away_goals': away_goals,
                'home_name': home,
                'away_name': away
            }
            
            # Solo guardamos el fixture_id para partidos activos (en curso o finalizados)
            if status in ['1H', '2H', 'HT', 'ET', 'P', 'FT', 'AET', 'PEN']:
                fixture_ids[match_key] = fixture_id
            
    # Consultar eventos (goles, tarjetas) de cada partido activo
    eventos_partido = {}  # match_key → texto formateado de eventos
    for match_key, fid in fixture_ids.items():
        try:
            events_url = f"https://v3.football.api-sports.io/fixtures/events?fixture={fid}"
            events_response = requests.get(events_url, headers=headers)
            events_data = events_response.json()
            events_list = events_data.get('response', [])
            
            goles = []
            tarjetas = []
            
            for ev in events_list:
                tipo = ev.get('type', '')
                detalle = ev.get('detail', '')
                jugador = ev.get('player', {}).get('name', 'Desconocido')
                tiempo = ev.get('time', {}).get('elapsed', '')
                extra = ev.get('time', {}).get('extra')
                
                # Formatear el minuto (ej: 45+2')
                if extra:
                    min_str = f"{tiempo}+{extra}'"
                else:
                    min_str = f"{tiempo}'"
                
                if tipo == 'Goal':
                    if detalle == 'Own Goal':
                        goles.append(f"⚽🔴 {jugador} {min_str} (Autogol)")
                    elif detalle == 'Penalty':
                        goles.append(f"⚽🅿️ {jugador} {min_str} (Penal)")
                    elif detalle == 'Missed Penalty':
                        goles.append(f"❌🅿️ {jugador} {min_str} (Penal Fallado)")
                    else:
                        goles.append(f"⚽ {jugador} {min_str}")
                elif tipo == 'Card':
                    if 'Yellow' in detalle and 'Red' not in detalle:
                        tarjetas.append(f"🟨 {jugador} {min_str}")
                    elif 'Red' in detalle:
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
                    
                    resultado_str = f" [{home_goals}] - [{away_goals}] "
                    
                    if " vs " in summary:
                        nuevo_summary = summary.replace(" vs ", resultado_str)
                    else:
                        nuevo_summary = re.sub(r" \[\d+\] - \[\d+\] ", resultado_str, summary)
                        
                    # Limpiar cualquier estado anterior entre paréntesis
                    nuevo_summary = re.sub(r" \([^)]*\)$", "", nuevo_summary)
                    
                    status = res['status']
                    elapsed = res.get('elapsed')
                    
                    if status in ["FT", "AET", "PEN"]:
                        nuevo_summary = nuevo_summary.replace("⚽", "✅").replace("🏆", "✅")
                        nuevo_summary += " (Final)"
                    elif status == "HT":
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        nuevo_summary += " (Medio Tiempo)"
                    elif status == "ET":
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        nuevo_summary += " (Tiempo Extra)"
                    elif status == "P":
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        nuevo_summary += " (Penales)"
                    elif status in ["1H", "2H"]:
                        nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                        if elapsed:
                            nuevo_summary += f" (Min. {elapsed}')"
                        else:
                            nuevo_summary += " (En Vivo)"
                            
                    comp_dinamico['summary'] = nuevo_summary
                    
                    # Inyectar eventos (goles/tarjetas) en la DESCRIPTION
                    if match_key in eventos_partido:
                        desc_existente = str(comp_dinamico.get('description', ''))
                        # Limpiar descripción de eventos anterior si existe
                        desc_existente = re.sub(
                            r'(\n?---\n⚽ GOLES:.*|\n?---\n📋 TARJETAS:.*)',
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
                    if status in ["FT", "AET", "PEN"]:
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
