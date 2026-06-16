import os
from icalendar import Calendar, vDatetime
from datetime import timedelta

# Mapping of cities to their offsets to reach El Salvador time (UTC-6)
offset_map = {
    # PDT (+1 hour)
    "BC Place\\, Vancouver": 1,
    "Lumen Field\\, Seattle": 1,
    "Levi's Stadium\\, San Francisco": 1,
    "SoFi Stadium\\, Los Ángeles": 1,
    
    # CST (0 hours)
    "Estadio Akron\\, Guadalajara": 0,
    "Estadio BBVA\\, Monterrey": 0,
    "Estadio Azteca\\, Ciudad de México": 0,
    
    # CDT (-1 hour)
    "AT&T Stadium\\, Dallas": -1,
    "NRG Stadium\\, Houston": -1,
    "Arrowhead Stadium\\, Kansas City": -1,
    
    # EDT (-2 hours)
    "Mercedes-Benz Stadium\\, Atlanta": -2,
    "Hard Rock Stadium\\, Miami": -2,
    "BMO Field\\, Toronto": -2,
    "Gillette Stadium\\, Boston": -2,
    "Lincoln Financial Field\\, Filadelfia": -2,
    "MetLife Stadium\\, Nueva York/NJ": -2,
    "MetLife Stadium\\, Nueva York/Nueva Jersey": -2,
}

def fix_calendar_times(filepath):
    print(f"Procesando {filepath}...")
    try:
        with open(filepath, 'rb') as f:
            cal_data = f.read()
            cal = Calendar.from_ical(cal_data)
    except FileNotFoundError:
        print(f"Archivo {filepath} no encontrado.")
        return

    modificados = 0
    for component in cal.walk():
        if component.name == "VEVENT":
            location = str(component.get('location', ''))
            
            offset_hours = 0
            for loc_key, off in offset_map.items():
                if loc_key.replace('\\,', ',') in location.replace('\\,', ',') or loc_key in location:
                    offset_hours = off
                    break
                    
            if offset_hours != 0:
                for prop in ['dtstart', 'dtend']:
                    if prop in component:
                        dt = component[prop].dt
                        new_dt = dt + timedelta(hours=offset_hours)
                        new_vdt = vDatetime(new_dt)
                        new_vdt.params = component[prop].params
                        component[prop] = new_vdt
                        
                modificados += 1

    with open(filepath, 'wb') as f:
        f.write(cal.to_ical())
    print(f"Se corrigieron {modificados} eventos en {filepath}.")

if __name__ == "__main__":
    files_to_fix = [
        "base_mundial.ics",
        "mundial_2026.ics",
        "mundial_2026_dinamico.ics"
    ]
    for file in files_to_fix:
        fix_calendar_times(file)
