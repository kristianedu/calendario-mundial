import json
from icalendar import Calendar
import re

def generar_calendario_dinamico():
    print("Iniciando actualización del calendario...")
    
    # Leer resultados simulados
    try:
        with open('resultados.json', 'r', encoding='utf-8') as f:
            resultados = json.load(f)
    except FileNotFoundError:
        print("No se encontró resultados.json, usando base vacía.")
        resultados = {}

    # Leer calendario base
    with open('base_mundial.ics', 'rb') as f:
        cal = Calendar.from_ical(f.read())

    # Procesar eventos
    modificados = 0
    for component in cal.walk():
        if component.name == "VEVENT":
            uid = str(component.get('uid'))
            if uid in resultados:
                res = resultados[uid]
                
                summary = str(component.get('summary'))
                desc = str(component.get('description', ''))
                
                score_home = res.get('score_home', 0)
                score_away = res.get('score_away', 0)
                status = res.get('status', '')
                notes = res.get('notes', '')

                # Formatear el resultado
                resultado_str = f" [{score_home}] - [{score_away}] "
                
                # Actualizar el título cambiando " vs " por el resultado
                if " vs " in summary:
                    nuevo_summary = summary.replace(" vs ", resultado_str)
                else:
                    nuevo_summary = f"{summary} {resultado_str.strip()}"
                
                # Añadir estado al título si está terminado o en juego
                if status == "FINISHED":
                    nuevo_summary = nuevo_summary.replace("⚽", "✅").replace("🏆", "✅")
                    nuevo_summary += " (Final)"
                elif status == "IN_PLAY":
                    nuevo_summary = nuevo_summary.replace("⚽", "🔴").replace("🏆", "🔴")
                    nuevo_summary += f" (En Vivo)"

                # Actualizar componente
                component['summary'] = nuevo_summary
                
                # Añadir nota a la descripción
                if notes:
                    component['description'] = f"{notes}\n\n{desc}"
                
                modificados += 1

    # Guardar nuevo calendario
    output_file = 'mundial_2026_dinamico.ics'
    with open(output_file, 'wb') as f:
        f.write(cal.to_ical())
        
    print(f"Calendario actualizado con éxito en '{output_file}'. Se actualizaron {modificados} partidos.")

if __name__ == "__main__":
    generar_calendario_dinamico()
