import icalendar
from datetime import datetime, timedelta

# Horarios correctos en hora de El Salvador (UTC-6)
# Match name substring -> (year, month, day, hour, minute)
FINAL_MATCHES = {
    "Semifinal 1": (2026, 7, 14, 13, 0),
    "Semifinal 2": (2026, 7, 15, 13, 0),
    "Tercer Lugar": (2026, 7, 18, 15, 0),
    "GRAN FINAL": (2026, 7, 19, 13, 0)
}

def fix_finals(filepath):
    print(f"\n{'='*60}")
    print(f"Procesando Finales en: {filepath}")
    print(f"{'='*60}")

    try:
        with open(filepath, 'rb') as f:
            cal = icalendar.Calendar.from_ical(f.read())
    except FileNotFoundError:
        print(f"  ❌ Archivo no encontrado: {filepath}")
        return

    modificados = 0
    sin_cambio = 0

    for component in cal.walk('VEVENT'):
        summary = str(component.get('summary', ''))
        
        match_time = None
        for key, time_tuple in FINAL_MATCHES.items():
            if key in summary:
                match_time = time_tuple
                break

        if match_time:
            year, month, day, hour, minute = match_time
            new_start = datetime(year, month, day, hour, minute, 0)
            new_end = new_start + timedelta(hours=2)

            current_start = component['dtstart'].dt
            current_start_str = current_start.strftime("%Y-%m-%d %H:%M") if hasattr(current_start, 'strftime') else str(current_start)
            new_start_str = new_start.strftime("%Y-%m-%d %H:%M")

            if current_start_str != new_start_str:
                params_start = component['dtstart'].params
                new_vdt_start = icalendar.vDatetime(new_start)
                new_vdt_start.params = params_start
                component['dtstart'] = new_vdt_start

                if 'dtend' in component:
                    params_end = component['dtend'].params
                    new_vdt_end = icalendar.vDatetime(new_end)
                    new_vdt_end.params = params_end
                    component['dtend'] = new_vdt_end

                print(f"  ✅ {summary[:60]}...")
                print(f"     {current_start_str} → {new_start_str}")
                modificados += 1
            else:
                sin_cambio += 1

    with open(filepath, 'wb') as f:
        f.write(cal.to_ical())
        
    print(f"\n  📊 Resumen: {modificados} corregidos, {sin_cambio} ya estaban bien")

if __name__ == "__main__":
    files = [
        "base_mundial.ics",
        "mundial_2026.ics",
        "mundial_2026_dinamico.ics",
    ]
    for f in files:
        fix_finals(f)
