"""
Script para corregir los horarios de los partidos del Mundial 2026
en los archivos ICS, poniendo la hora exacta de El Salvador (UTC-6).

Los horarios se obtuvieron de fuentes oficiales (FIFA, Google, Fox Sports).
"""
from icalendar import Calendar, vDatetime
from datetime import datetime

# Horarios correctos en hora de El Salvador (UTC-6 / CST)
# Formato: UID → (año, mes, día, hora, minuto)
# Para DTEND sumamos 2 horas a cada DTSTART

CORRECT_TIMES = {
    # Jornada 1
    "wc2026-GS-001@mundial2026": (2026, 6, 11, 13, 0),   # México vs Sudáfrica - 1:00 PM SV
    "wc2026-GS-002@mundial2026": (2026, 6, 11, 20, 0),   # Corea del Sur vs Chequia - 8:00 PM SV
    "wc2026-GS-003@mundial2026": (2026, 6, 12, 13, 0),   # Canadá vs Bosnia - 1:00 PM SV
    "wc2026-GS-004@mundial2026": (2026, 6, 12, 19, 0),   # EE.UU. vs Paraguay - 7:00 PM SV
    "wc2026-GS-005@mundial2026": (2026, 6, 13, 13, 0),   # Qatar vs Suiza - 1:00 PM SV
    "wc2026-GS-006@mundial2026": (2026, 6, 13, 16, 0),   # Brasil vs Marruecos - 4:00 PM SV
    "wc2026-GS-007@mundial2026": (2026, 6, 13, 19, 0),   # Haití vs Escocia - 7:00 PM SV
    "wc2026-GS-008@mundial2026": (2026, 6, 13, 22, 0),   # Australia vs Turquía - 10:00 PM SV
    "wc2026-GS-009@mundial2026": (2026, 6, 14, 11, 0),   # Alemania vs Curazao - 11:00 AM SV
    "wc2026-GS-010@mundial2026": (2026, 6, 14, 14, 0),   # Países Bajos vs Japón - 2:00 PM SV
    "wc2026-GS-011@mundial2026": (2026, 6, 14, 17, 0),   # Costa de Marfil vs Ecuador - 5:00 PM SV
    "wc2026-GS-012@mundial2026": (2026, 6, 14, 20, 0),   # Suecia vs Túnez - 8:00 PM SV
    "wc2026-GS-013@mundial2026": (2026, 6, 15, 10, 0),   # España vs Cabo Verde - 10:00 AM SV (12 PM ET)
    "wc2026-GS-014@mundial2026": (2026, 6, 15, 13, 0),   # Bélgica vs Egipto - 1:00 PM SV (3 PM ET)
    "wc2026-GS-015@mundial2026": (2026, 6, 15, 16, 0),   # Irán vs Nueva Zelanda - 4:00 PM SV (6 PM ET)
    "wc2026-GS-016@mundial2026": (2026, 6, 15, 19, 0),   # Arabia Saudita vs Uruguay - 7:00 PM SV (9 PM ET)

    # Jornada 1 cont.
    "wc2026-GS-017@mundial2026": (2026, 6, 16, 13, 0),   # Francia vs Senegal - 1:00 PM SV
    "wc2026-GS-018@mundial2026": (2026, 6, 16, 16, 0),   # Irak vs Noruega - 4:00 PM SV
    "wc2026-GS-019@mundial2026": (2026, 6, 16, 19, 0),   # Argentina vs Argelia - 7:00 PM SV
    "wc2026-GS-020@mundial2026": (2026, 6, 16, 22, 0),   # Austria vs Jordania - 10:00 PM SV
    "wc2026-GS-021@mundial2026": (2026, 6, 17, 11, 0),   # Portugal vs RD Congo - 11:00 AM SV
    "wc2026-GS-022@mundial2026": (2026, 6, 17, 14, 0),   # Ghana vs Panamá - 2:00 PM SV (wait, browser says Ghana vs Panamá 5pm)

    # Wait, let me re-check June 17 from browser data:
    # Portugal vs RD Congo: 11:00 a.m.
    # Inglaterra vs Croacia: 2:00 p.m.
    # Ghana vs Panamá: 5:00 p.m.
    # Uzbekistán vs Colombia: 8:00 p.m.
    # But original ICS order for June 17: GS-021 Portugal, GS-022 Ghana, GS-023 Uzbekistán, GS-024 Inglaterra
    # Need to match by UID, not order. Let me check the original ICS UIDs and match names.
}

# Let me take a different approach: match by team names in SUMMARY instead of assuming UID order

# Complete schedule with correct El Salvador times
# Format: (home_keyword, away_keyword) → (year, month, day, hour, minute)
SCHEDULE = {
    # June 11
    ("México", "Sudáfrica"): (2026, 6, 11, 13, 0),
    ("Corea del Sur", "Chequia"): (2026, 6, 11, 20, 0),

    # June 12
    ("Canadá", "Bosnia"): (2026, 6, 12, 13, 0),
    ("EE.UU.", "Paraguay"): (2026, 6, 12, 19, 0),

    # June 13
    ("Qatar", "Suiza"): (2026, 6, 13, 13, 0),
    ("Brasil", "Marruecos"): (2026, 6, 13, 16, 0),
    ("Haití", "Escocia"): (2026, 6, 13, 19, 0),
    ("Australia", "Turquía"): (2026, 6, 13, 22, 0),

    # June 14
    ("Alemania", "Curazao"): (2026, 6, 14, 11, 0),
    ("Países Bajos", "Japón"): (2026, 6, 14, 14, 0),
    ("Costa de Marfil", "Ecuador"): (2026, 6, 14, 17, 0),
    ("Suecia", "Túnez"): (2026, 6, 14, 20, 0),

    # June 15
    ("España", "Cabo Verde"): (2026, 6, 15, 10, 0),
    ("Bélgica", "Egipto"): (2026, 6, 15, 13, 0),
    ("Irán", "Nueva Zelanda"): (2026, 6, 15, 16, 0),
    ("Arabia Saudita", "Uruguay"): (2026, 6, 15, 19, 0),

    # June 16
    ("Francia", "Senegal"): (2026, 6, 16, 13, 0),
    ("Irak", "Noruega"): (2026, 6, 16, 16, 0),
    ("Argentina", "Argelia"): (2026, 6, 16, 19, 0),
    ("Austria", "Jordania"): (2026, 6, 16, 22, 0),

    # June 17
    ("Portugal", "RD Congo"): (2026, 6, 17, 11, 0),
    ("Inglaterra", "Croacia"): (2026, 6, 17, 14, 0),
    ("Ghana", "Panamá"): (2026, 6, 17, 17, 0),
    ("Uzbekistán", "Colombia"): (2026, 6, 17, 20, 0),

    # June 18 (Jornada 2)
    ("Chequia", "Sudáfrica"): (2026, 6, 18, 10, 0),
    ("Suiza", "Bosnia"): (2026, 6, 18, 13, 0),
    ("Canadá", "Qatar"): (2026, 6, 18, 16, 0),
    ("México", "Corea del Sur"): (2026, 6, 18, 19, 0),

    # June 19
    ("EE.UU.", "Australia"): (2026, 6, 19, 13, 0),
    ("Escocia", "Marruecos"): (2026, 6, 19, 16, 0),
    ("Brasil", "Haití"): (2026, 6, 19, 18, 30),
    ("Turquía", "Paraguay"): (2026, 6, 19, 21, 0),

    # June 20
    ("Países Bajos", "Suecia"): (2026, 6, 20, 11, 0),
    ("Alemania", "Costa de Marfil"): (2026, 6, 20, 14, 0),
    ("Ecuador", "Curazao"): (2026, 6, 20, 18, 0),
    ("Túnez", "Japón"): (2026, 6, 20, 22, 0),

    # June 21
    ("España", "Arabia Saudita"): (2026, 6, 21, 10, 0),
    ("Bélgica", "Irán"): (2026, 6, 21, 13, 0),
    ("Uruguay", "Cabo Verde"): (2026, 6, 21, 16, 0),
    ("Nueva Zelanda", "Egipto"): (2026, 6, 21, 19, 0),

    # June 22
    ("Argentina", "Austria"): (2026, 6, 22, 11, 0),
    ("Francia", "Irak"): (2026, 6, 22, 15, 0),
    ("Noruega", "Senegal"): (2026, 6, 22, 18, 0),
    ("Jordania", "Argelia"): (2026, 6, 22, 21, 0),

    # June 23
    ("Portugal", "Uzbekistán"): (2026, 6, 23, 11, 0),
    ("Inglaterra", "Ghana"): (2026, 6, 23, 14, 0),
    ("Panamá", "Croacia"): (2026, 6, 23, 17, 0),
    ("Colombia", "RD Congo"): (2026, 6, 23, 20, 0),

    # June 24 (Jornada 3)
    ("Suiza", "Canadá"): (2026, 6, 24, 13, 0),
    ("Bosnia", "Qatar"): (2026, 6, 24, 13, 0),
    ("Escocia", "Brasil"): (2026, 6, 24, 16, 0),
    ("Marruecos", "Haití"): (2026, 6, 24, 16, 0),
    ("Chequia", "México"): (2026, 6, 24, 19, 0),
    ("Sudáfrica", "Corea del Sur"): (2026, 6, 24, 19, 0),

    # June 25 (ET times from search: 4PM, 4PM, 7PM, 7PM, 10PM, 10PM → SV: 2PM, 2PM, 5PM, 5PM, 8PM, 8PM)
    ("Curazao", "Costa de Marfil"): (2026, 6, 25, 14, 0),
    ("Ecuador", "Alemania"): (2026, 6, 25, 14, 0),
    ("Túnez", "Países Bajos"): (2026, 6, 25, 17, 0),
    ("Japón", "Suecia"): (2026, 6, 25, 17, 0),
    ("Turquía", "EE.UU."): (2026, 6, 25, 20, 0),
    ("Paraguay", "Australia"): (2026, 6, 25, 20, 0),

    # June 26 (ET: 3PM, 3PM, 8PM, 8PM, 11PM, 11PM → SV: 1PM, 1PM, 6PM, 6PM, 9PM, 9PM)
    ("Noruega", "Francia"): (2026, 6, 26, 13, 0),
    ("Senegal", "Irak"): (2026, 6, 26, 13, 0),
    ("Cabo Verde", "Arabia Saudita"): (2026, 6, 26, 18, 0),
    ("Uruguay", "España"): (2026, 6, 26, 18, 0),
    ("Egipto", "Irán"): (2026, 6, 26, 21, 0),
    ("Nueva Zelanda", "Bélgica"): (2026, 6, 26, 21, 0),

    # June 27 (ET: 5PM, 5PM, 7:30PM, 7:30PM, 11PM, 11PM → SV: 3PM, 3PM, 5:30PM, 5:30PM, 9PM, 9PM)
    ("Panamá", "Inglaterra"): (2026, 6, 27, 15, 0),
    ("Croacia", "Ghana"): (2026, 6, 27, 15, 0),
    ("RD Congo", "Uzbekistán"): (2026, 6, 27, 17, 30),
    ("Colombia", "Portugal"): (2026, 6, 27, 17, 30),  # Search says: Portugal vs Colombia → Colombia vs Portugal in ICS is the J3
    ("Portugal", "Colombia"): (2026, 6, 27, 17, 30),
    ("Jordania", "Argentina"): (2026, 6, 27, 21, 0),
    ("Argelia", "Austria"): (2026, 6, 27, 21, 0),
}

from datetime import timedelta

def find_match(summary, schedule):
    """Find the correct time for a match by checking team names in the summary."""
    for (home, away), time_tuple in schedule.items():
        if home in summary and away in summary:
            return time_tuple
    return None

def fix_calendar(filepath):
    print(f"\n{'='*60}")
    print(f"Procesando: {filepath}")
    print(f"{'='*60}")

    try:
        with open(filepath, 'rb') as f:
            cal = Calendar.from_ical(f.read())
    except FileNotFoundError:
        print(f"  ❌ Archivo no encontrado: {filepath}")
        return

    modificados = 0
    sin_cambio = 0

    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get('summary', ''))
            uid = str(component.get('uid', ''))

            match_time = find_match(summary, SCHEDULE)

            if match_time:
                year, month, day, hour, minute = match_time
                new_start = datetime(year, month, day, hour, minute, 0)
                new_end = new_start + timedelta(hours=2)

                # Get current time for comparison
                current_start = component['dtstart'].dt
                current_start_str = current_start.strftime("%Y-%m-%d %H:%M") if hasattr(current_start, 'strftime') else str(current_start)

                new_start_str = new_start.strftime("%Y-%m-%d %H:%M")

                if current_start_str != new_start_str:
                    # Update DTSTART
                    params_start = component['dtstart'].params
                    new_vdt_start = vDatetime(new_start)
                    new_vdt_start.params = params_start
                    component['dtstart'] = new_vdt_start

                    # Update DTEND
                    if 'dtend' in component:
                        params_end = component['dtend'].params
                        new_vdt_end = vDatetime(new_end)
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
        fix_calendar(f)
    print("\n🎉 ¡Listo! Todos los calendarios actualizados con hora de El Salvador.")
