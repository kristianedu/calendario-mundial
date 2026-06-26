"""
generar_bracket.py
Genera bracket_data.json a partir de base_mundial.ics
para alimentar la página visual del bracket del Mundial 2026.

La estructura del bracket sigue el cuadro OFICIAL de la FIFA 2026
(partidos 73-104 -> KO-001..KO-032). Cada cruce se llena en este orden
de prioridad:

  1. Equipos reales ya asignados en el .ics (post-sorteo / con marcador).
  2. Proyección a partir de la tabla de posiciones de los grupos
     (1º/2º de grupo y mejores terceros).
  3. Propagación del ganador de un cruce ya finalizado.
  4. Etiqueta de origen (ej. "1°E", "G·T2") cuando aún no se puede definir.
"""
import json
import re
from datetime import datetime
from collections import defaultdict
from icalendar import Calendar
from equipos import get_bandera, get_codigo

# Meses en español abreviados
MESES_ES = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"
}

# ═══════════════════════════════════════════════════════════════════
#  ESTRUCTURA OFICIAL DEL CUADRO FIFA 2026 (partidos 73-104)
#  KO-num -> { round, side, order, t1, t2 }
#  - round : ronda del bracket
#  - side  : 'left' / 'right' / 'center' (mitad del cuadro)
#  - order : orden vertical dentro de su lado (de arriba a abajo)
#  - t1/t2 : origen de cada equipo:
#       ('pos', '1A')        -> 1º del grupo A
#       ('pos', '2B')        -> 2º del grupo B
#       ('third', [grupos])  -> uno de los mejores terceros (grupos permitidos)
#       ('w', n)             -> ganador del cruce KO-n
#       ('l', n)             -> perdedor del cruce KO-n
#  Las dos mitades convergen: 'left' alimenta la Semifinal 1 (KO-029),
#  'right' alimenta la Semifinal 2 (KO-030).
# ═══════════════════════════════════════════════════════════════════
BRACKET = {
    # ─── Treintaidosavos (Round of 32) — mitad IZQUIERDA ───
    2:  dict(round="round_of_32", side="left",  order=0, t1=("pos", "1E"), t2=("third", ["A", "C", "D", "F"])),
    5:  dict(round="round_of_32", side="left",  order=1, t1=("pos", "1I"), t2=("third", ["C", "D", "F", "G", "H"])),
    1:  dict(round="round_of_32", side="left",  order=2, t1=("pos", "2A"), t2=("pos", "2B")),
    3:  dict(round="round_of_32", side="left",  order=3, t1=("pos", "1F"), t2=("pos", "2C")),
    11: dict(round="round_of_32", side="left",  order=4, t1=("pos", "2K"), t2=("pos", "2L")),
    12: dict(round="round_of_32", side="left",  order=5, t1=("pos", "1H"), t2=("pos", "2J")),
    9:  dict(round="round_of_32", side="left",  order=6, t1=("pos", "1D"), t2=("third", ["B", "E", "F", "I", "J"])),
    10: dict(round="round_of_32", side="left",  order=7, t1=("pos", "1G"), t2=("third", ["A", "E", "H", "I", "J"])),
    # ─── Treintaidosavos (Round of 32) — mitad DERECHA ───
    4:  dict(round="round_of_32", side="right", order=0, t1=("pos", "1C"), t2=("pos", "2F")),
    6:  dict(round="round_of_32", side="right", order=1, t1=("pos", "2E"), t2=("pos", "2I")),
    7:  dict(round="round_of_32", side="right", order=2, t1=("pos", "1A"), t2=("third", ["C", "E", "H"])),
    8:  dict(round="round_of_32", side="right", order=3, t1=("pos", "1L"), t2=("third", ["E", "I", "J", "K"])),
    14: dict(round="round_of_32", side="right", order=4, t1=("pos", "1J"), t2=("pos", "2H")),
    16: dict(round="round_of_32", side="right", order=5, t1=("pos", "2D"), t2=("pos", "2G")),
    13: dict(round="round_of_32", side="right", order=6, t1=("pos", "1B"), t2=("third", ["E", "F", "G", "I", "J"])),
    15: dict(round="round_of_32", side="right", order=7, t1=("pos", "1K"), t2=("third", ["D", "E", "I", "J", "L"])),
    # ─── Octavos (Round of 16) ───
    17: dict(round="round_of_16", side="left",  order=0, t1=("w", 2),  t2=("w", 5)),
    18: dict(round="round_of_16", side="left",  order=1, t1=("w", 1),  t2=("w", 3)),
    21: dict(round="round_of_16", side="left",  order=2, t1=("w", 11), t2=("w", 12)),
    22: dict(round="round_of_16", side="left",  order=3, t1=("w", 9),  t2=("w", 10)),
    19: dict(round="round_of_16", side="right", order=0, t1=("w", 4),  t2=("w", 6)),
    20: dict(round="round_of_16", side="right", order=1, t1=("w", 7),  t2=("w", 8)),
    23: dict(round="round_of_16", side="right", order=2, t1=("w", 14), t2=("w", 16)),
    24: dict(round="round_of_16", side="right", order=3, t1=("w", 13), t2=("w", 15)),
    # ─── Cuartos (Quarter-finals) ───
    25: dict(round="quarter_finals", side="left",  order=0, t1=("w", 17), t2=("w", 18)),
    26: dict(round="quarter_finals", side="left",  order=1, t1=("w", 21), t2=("w", 22)),
    27: dict(round="quarter_finals", side="right", order=0, t1=("w", 19), t2=("w", 20)),
    28: dict(round="quarter_finals", side="right", order=1, t1=("w", 23), t2=("w", 24)),
    # ─── Semifinales ───
    29: dict(round="semi_finals", side="left",  order=0, t1=("w", 25), t2=("w", 26)),
    30: dict(round="semi_finals", side="right", order=0, t1=("w", 27), t2=("w", 28)),
    # ─── Tercer lugar y Final ───
    31: dict(round="third_place", side="center", order=0, t1=("l", 29), t2=("l", 30)),
    32: dict(round="final",       side="center", order=0, t1=("w", 29), t2=("w", 30)),
}

# Slots de "mejor tercero" con sus grupos permitidos (para el emparejamiento)
THIRD_SLOTS = {ko: spec["t2"][1] for ko, spec in BRACKET.items()
               if spec["t2"][0] == "third"}


def parsear_equipo_del_summary(summary):
    """Extrae los dos equipos, marcadores y estado de un SUMMARY del .ics."""
    result = {
        "team1": None, "team2": None,
        "score1": None, "score2": None,
        "status": "pending",
    }

    if "(Final)" in summary:
        result["status"] = "finished"
    elif "(En Vivo)" in summary or "(Medio Tiempo)" in summary or \
         "(Tiempo Extra)" in summary or "(Penales)" in summary:
        result["status"] = "live"

    match_score = re.search(
        r'(?:[\U0001F1E0-\U0001F1FF]{2}|[\U0001F3F4][\U000E0061-\U000E007A]+[\U000E007F])\s+'
        r'(.+?)\s+\[(\d+)\]\s*-\s*\[(\d+)\]\s+(.+?)\s+'
        r'(?:[\U0001F1E0-\U0001F1FF]{2}|[\U0001F3F4][\U000E0061-\U000E007A]+[\U000E007F])',
        summary
    )
    if match_score:
        result["team1"] = match_score.group(1).strip()
        result["score1"] = int(match_score.group(2))
        result["score2"] = int(match_score.group(3))
        result["team2"] = match_score.group(4).strip()
        return result

    match_vs = re.search(
        r'(?:[\U0001F1E0-\U0001F1FF]{2}|[\U0001F3F4][\U000E0061-\U000E007A]+[\U000E007F])\s+'
        r'(.+?)\s+vs\s+(.+?)\s+'
        r'(?:[\U0001F1E0-\U0001F1FF]{2}|[\U0001F3F4][\U000E0061-\U000E007A]+[\U000E007F])',
        summary
    )
    if match_vs:
        result["team1"] = match_vs.group(1).strip()
        result["team2"] = match_vs.group(2).strip()
        return result

    return result


def formatear_fecha(dt):
    """Convierte datetime a formato '28 jun'."""
    mes = MESES_ES.get(dt.month, str(dt.month))
    return f"{dt.day} {mes}"


def team_obj(nombre, score=None):
    """Construye el objeto de equipo (equipo real) para el JSON."""
    return {
        "name": get_codigo(nombre),
        "flag": get_bandera(nombre),
        "fullName": nombre,
        "score": score,
        "placeholder": False,
    }


def slot_obj(name, full):
    """Construye un placeholder (slot sin equipo definido)."""
    return {
        "name": name,
        "flag": "🛡️",
        "fullName": full,
        "score": None,
        "placeholder": True,
    }


def etiqueta_corta(ko_num):
    """Etiqueta corta de un cruce para usar en placeholders (ej. 'T2', 'O1')."""
    if 1 <= ko_num <= 16:
        return f"T{ko_num}"          # Treintaidosavos
    if 17 <= ko_num <= 24:
        return f"O{ko_num - 16}"     # Octavos
    if 25 <= ko_num <= 28:
        return f"C{ko_num - 24}"     # Cuartos
    if 29 <= ko_num <= 30:
        return f"S{ko_num - 28}"     # Semifinal
    return f"P{ko_num}"


# ═══════════════════════════════════════════════════════════════════
#  TABLAS DE GRUPOS
# ═══════════════════════════════════════════════════════════════════
def extraer_grupo(description):
    match = re.search(r'Grupo ([A-L])', description)
    return match.group(1) if match else None


def parsear_resultado_grupo(summary):
    finalizado = "(Final)" in summary or "✅" in summary

    match_score = re.search(
        r'(?:[\U0001F1E0-\U0001F1FF]{2}|[\U0001F3F4][\U000E0061-\U000E007A]+[\U000E007F])\s+'
        r'(.+?)\s+\[(\d+)\]\s*-\s*\[(\d+)\]\s+(.+?)\s+'
        r'(?:[\U0001F1E0-\U0001F1FF]{2}|[\U0001F3F4][\U000E0061-\U000E007A]+[\U000E007F])',
        summary
    )
    if match_score:
        return (match_score.group(1).strip(), match_score.group(4).strip(),
                int(match_score.group(2)), int(match_score.group(3)), finalizado)

    match_vs = re.search(
        r'(?:[\U0001F1E0-\U0001F1FF]{2}|[\U0001F3F4][\U000E0061-\U000E007A]+[\U000E007F])\s+'
        r'(.+?)\s+vs\s+(.+?)\s+'
        r'(?:[\U0001F1E0-\U0001F1FF]{2}|[\U0001F3F4][\U000E0061-\U000E007A]+[\U000E007F])',
        summary
    )
    if match_vs:
        return (match_vs.group(1).strip(), match_vs.group(2).strip(), None, None, False)

    return None


def calcular_tablas_grupos(cal):
    """Calcula las tablas de posiciones de todos los grupos desde el ICS."""
    grupos = defaultdict(lambda: defaultdict(lambda: {
        "pts": 0, "gf": 0, "gc": 0, "dg": 0,
        "pj": 0, "pg": 0, "pe": 0, "pp": 0
    }))
    partidos_grupo = defaultdict(lambda: {"total": 0, "jugados": 0})

    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get('uid', ''))
        if not uid.startswith('wc2026-GS'):
            continue

        summary = str(component.get('summary', ''))
        description = str(component.get('description', ''))
        grupo = extraer_grupo(description) or extraer_grupo(summary)
        if not grupo:
            continue

        resultado = parsear_resultado_grupo(summary)
        if resultado is None:
            continue

        equipo1, equipo2, goles1, goles2, finalizado = resultado
        _ = grupos[grupo][equipo1]
        _ = grupos[grupo][equipo2]
        partidos_grupo[grupo]["total"] += 1

        if finalizado and goles1 is not None and goles2 is not None:
            partidos_grupo[grupo]["jugados"] += 1
            grupos[grupo][equipo1]["pj"] += 1
            grupos[grupo][equipo1]["gf"] += goles1
            grupos[grupo][equipo1]["gc"] += goles2
            grupos[grupo][equipo1]["dg"] += (goles1 - goles2)
            grupos[grupo][equipo2]["pj"] += 1
            grupos[grupo][equipo2]["gf"] += goles2
            grupos[grupo][equipo2]["gc"] += goles1
            grupos[grupo][equipo2]["dg"] += (goles2 - goles1)

            if goles1 > goles2:
                grupos[grupo][equipo1]["pts"] += 3
                grupos[grupo][equipo1]["pg"] += 1
                grupos[grupo][equipo2]["pp"] += 1
            elif goles2 > goles1:
                grupos[grupo][equipo2]["pts"] += 3
                grupos[grupo][equipo2]["pg"] += 1
                grupos[grupo][equipo1]["pp"] += 1
            else:
                grupos[grupo][equipo1]["pts"] += 1
                grupos[grupo][equipo1]["pe"] += 1
                grupos[grupo][equipo2]["pts"] += 1
                grupos[grupo][equipo2]["pe"] += 1

    tablas = {}
    for letra in sorted(grupos.keys()):
        equipos_grupo = []
        for equipo, stats in grupos[letra].items():
            equipos_grupo.append({
                "name": get_codigo(equipo),
                "fullName": equipo,
                "flag": get_bandera(equipo),
                "pts": stats["pts"], "pj": stats["pj"],
                "pg": stats["pg"], "pe": stats["pe"], "pp": stats["pp"],
                "gf": stats["gf"], "gc": stats["gc"], "dg": stats["dg"],
            })

        equipos_grupo.sort(key=lambda x: (-x["pts"], -x["dg"], -x["gf"]))

        # Eliminación matemática: cada equipo juega 3 partidos en el grupo.
        # maxPts = puntos actuales + 3 por cada partido que le falta.
        # Un equipo no puede entrar a la fase final (ni como 3º) si al menos
        # 3 rivales ya tienen MÁS puntos de los que él puede llegar a alcanzar.
        for eq in equipos_grupo:
            restantes = max(0, 3 - eq["pj"])
            eq["maxPts"] = eq["pts"] + 3 * restantes
        for eq in equipos_grupo:
            arriba_seguro = sum(1 for o in equipos_grupo
                                if o is not eq and o["pts"] > eq["maxPts"])
            eq["eliminated"] = arriba_seguro >= 3

        for i, eq in enumerate(equipos_grupo):
            eq["pos"] = i + 1
            if eq["eliminated"]:
                eq["status"] = "eliminated"
            elif i < 2:
                eq["status"] = "qualified"   # proyectado: 1º/2º
            elif i == 2:
                eq["status"] = "possible"    # proyectado: mejor tercero
            else:
                eq["status"] = "contention"  # 4º pero aún con opciones

        info = partidos_grupo[letra]
        tablas[letra] = {
            "teams": equipos_grupo,
            "played": info["jugados"],
            "total": info["total"],
            "complete": info["jugados"] == info["total"] and info["total"] > 0,
        }

    return tablas


def calcular_mejores_terceros(tablas):
    """Devuelve {grupo: equipo} de los 8 mejores terceros y marca su status."""
    terceros = []
    for letra, info in tablas.items():
        if len(info["teams"]) >= 3:
            eq = info["teams"][2]
            if eq.get("eliminated"):
                continue  # no consideramos terceros ya eliminados
            eq = eq.copy()
            eq["grupo"] = letra
            terceros.append(eq)

    terceros.sort(key=lambda x: (-x["pts"], -x["dg"], -x["gf"]))
    mejores = terceros[:8]
    grupos_clasificados = {t["grupo"] for t in mejores}

    # Marcar el status del tercero de cada grupo en base a los mejores terceros:
    #   - entre los 8 mejores            -> qualified
    #   - grupo cerrado o sin chance      -> eliminated
    #   - aún en juego y con opciones     -> possible (pelea un cupo de tercero)
    for letra, info in tablas.items():
        if len(info["teams"]) >= 3:
            tercero = info["teams"][2]
            if letra in grupos_clasificados:
                tercero["status"] = "qualified"
            elif info["complete"] or tercero.get("eliminated"):
                tercero["status"] = "eliminated"
            else:
                tercero["status"] = "possible"

    return {t["grupo"]: t for t in mejores}


def construir_tabla_terceros(tablas, mejores_terceros):
    """
    Tabla de los 12 terceros de grupo, ordenada por los criterios FIFA
    (puntos → diferencia de goles → goles a favor). Marca como 'qualified'
    a los 8 que clasifican.
    """
    filas = []
    grupos_clasificados = set(mejores_terceros.keys())
    for letra, info in tablas.items():
        if len(info["teams"]) < 3:
            continue
        t = info["teams"][2]
        filas.append({
            "group": letra,
            "name": t["name"],
            "flag": t["flag"],
            "fullName": t["fullName"],
            "pj": t["pj"], "pg": t["pg"], "pe": t["pe"], "pp": t["pp"],
            "gf": t["gf"], "gc": t["gc"], "dg": t["dg"], "pts": t["pts"],
            "qualified": letra in grupos_clasificados,
            "eliminated": bool(t.get("eliminated")),
        })

    filas.sort(key=lambda x: (-x["pts"], -x["dg"], -x["gf"]))
    for i, f in enumerate(filas):
        f["pos"] = i + 1
    return filas


def asignar_terceros(mejores_terceros):
    """
    Empareja los grupos de los mejores terceros con los slots '3°' del cuadro,
    respetando los grupos permitidos de cada slot (backtracking).
    Devuelve {ko_num: grupo}.
    """
    grupos_disponibles = set(mejores_terceros.keys())
    # Resolver primero los slots más restringidos
    slots = sorted(THIRD_SLOTS.items(), key=lambda kv: len(kv[1]))
    asignacion, usados = {}, set()

    def backtrack(i):
        if i == len(slots):
            return True
        ko, permitidos = slots[i]
        for g in permitidos:
            if g in grupos_disponibles and g not in usados:
                usados.add(g)
                asignacion[ko] = g
                if backtrack(i + 1):
                    return True
                usados.discard(g)
                del asignacion[ko]
        return False

    backtrack(0)
    return asignacion


# ═══════════════════════════════════════════════════════════════════
#  CONSTRUCCIÓN DEL BRACKET
# ═══════════════════════════════════════════════════════════════════
def leer_eventos_ko(cal):
    """Devuelve {ko_num: {team1, team2, score1, score2, status, date}}."""
    eventos = {}
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get('uid', ''))
        m = re.search(r'wc2026-KO-(\d+)', uid)
        if not m:
            continue
        ko_num = int(m.group(1))
        parsed = parsear_equipo_del_summary(str(component.get('summary', '')))
        parsed["date"] = formatear_fecha(component.get('dtstart').dt)
        eventos[ko_num] = parsed
    return eventos


def resolver_origen(spec, ko_num, tablas, terceros_asignacion, mejores_terceros,
                    ganadores, perdedores):
    """Resuelve el equipo de un slot según su origen. Devuelve un team/slot obj."""
    kind, val = spec

    if kind == "pos":
        pos, grp = int(val[0]), val[1]
        equipos = tablas.get(grp, {}).get("teams", [])
        if len(equipos) >= pos and not equipos[pos - 1].get("eliminated"):
            e = equipos[pos - 1]
            return {"name": e["name"], "flag": e["flag"],
                    "fullName": e["fullName"], "score": None, "placeholder": False}
        return slot_obj(f"{pos}°{grp}", f"{pos}º del Grupo {grp}")

    if kind == "third":
        grp = terceros_asignacion.get(ko_num)
        if grp and grp in mejores_terceros:
            e = mejores_terceros[grp]
            return {"name": e["name"], "flag": e["flag"],
                    "fullName": e["fullName"], "score": None, "placeholder": False}
        return slot_obj("3°", "Mejor tercer lugar")

    if kind == "w":
        if ganadores.get(val):
            return dict(ganadores[val], score=None)
        return slot_obj(f"G·{etiqueta_corta(val)}", f"Ganador {etiqueta_corta(val)}")

    if kind == "l":
        if perdedores.get(val):
            return dict(perdedores[val], score=None)
        return slot_obj(f"P·{etiqueta_corta(val)}", f"Perdedor {etiqueta_corta(val)}")

    return slot_obj("?", "Por definir")


def _fixture_team(nombre):
    """Objeto compacto de equipo para la pestaña Resumen."""
    return {"name": get_codigo(nombre), "flag": get_bandera(nombre), "fullName": nombre}


def extraer_fixtures(cal):
    """
    Extrae los partidos (grupos + eliminatorias) con equipos reales para la
    pestaña Resumen: últimos resultados y próximos partidos.
    """
    eventos = []
    for c in cal.walk():
        if c.name != "VEVENT":
            continue
        uid = str(c.get("uid", ""))
        es_gs = uid.startswith("wc2026-GS")
        es_ko = uid.startswith("wc2026-KO")
        if not (es_gs or es_ko):
            continue

        summary = str(c.get("summary", ""))
        p = parsear_equipo_del_summary(summary)
        if not p["team1"] or not p["team2"]:
            continue  # cruce aún sin equipos definidos

        dt = c.get("dtstart").dt
        try:
            orden = dt.replace(tzinfo=None)
        except (AttributeError, TypeError):
            orden = datetime(dt.year, dt.month, dt.day)

        if es_gs:
            desc = str(c.get("description", ""))
            mg = re.search(r"Grupo ([A-L])", desc) or re.search(r"Grupo ([A-L])", summary)
            comp = f"Grupo {mg.group(1)}" if mg else "Fase de grupos"
        else:
            comp = "Eliminatorias"

        eventos.append({
            "date": formatear_fecha(dt),
            "time": dt.strftime("%H:%M") if hasattr(dt, "hour") else "",
            "_sort": orden.isoformat(),
            "comp": comp,
            "team1": _fixture_team(p["team1"]),
            "team2": _fixture_team(p["team2"]),
            "score1": p["score1"],
            "score2": p["score2"],
            "status": p["status"],
        })

    finalizados = [e for e in eventos if e["status"] == "finished"]
    pendientes = [e for e in eventos if e["status"] != "finished"]
    finalizados.sort(key=lambda e: e["_sort"], reverse=True)
    pendientes.sort(key=lambda e: (e["status"] != "live", e["_sort"]))

    return {
        "recent": finalizados[:8],
        "upcoming": pendientes[:8],
    }


def generar_bracket():
    """Lee base_mundial.ics y genera bracket_data.json."""
    try:
        with open('base_mundial.ics', 'rb') as f:
            cal = Calendar.from_ical(f.read())
    except FileNotFoundError:
        print("❌ Archivo base_mundial.ics no encontrado.")
        return

    tablas = calcular_tablas_grupos(cal)
    mejores_terceros = calcular_mejores_terceros(tablas)
    tabla_terceros = construir_tabla_terceros(tablas, mejores_terceros)
    fixtures = extraer_fixtures(cal)
    terceros_asignacion = asignar_terceros(mejores_terceros)
    eventos_ko = leer_eventos_ko(cal)
    print(f"📊 Tablas: {len(tablas)} grupos | "
          f"{len(mejores_terceros)} mejores terceros asignados")

    ganadores, perdedores = {}, {}
    partidos = []

    # Procesar en orden de KO (las rondas posteriores dependen de las previas)
    for ko_num in sorted(BRACKET.keys()):
        spec = BRACKET[ko_num]
        ev = eventos_ko.get(ko_num, {"team1": None, "team2": None,
                                     "score1": None, "score2": None,
                                     "status": "pending", "date": ""})

        # Equipo 1: real (.ics) > origen del cuadro
        if ev["team1"]:
            t1 = team_obj(ev["team1"], ev["score1"])
        else:
            t1 = resolver_origen(spec["t1"], ko_num, tablas, terceros_asignacion,
                                 mejores_terceros, ganadores, perdedores)

        # Equipo 2: real (.ics) > origen del cuadro
        if ev["team2"]:
            t2 = team_obj(ev["team2"], ev["score2"])
        else:
            t2 = resolver_origen(spec["t2"], ko_num, tablas, terceros_asignacion,
                                 mejores_terceros, ganadores, perdedores)

        # Estado y ganador
        status = ev["status"]
        winner = None
        if status == "finished" and ev["score1"] is not None and ev["score2"] is not None:
            if ev["score1"] > ev["score2"]:
                winner = "team1"
                ganadores[ko_num] = t1
                perdedores[ko_num] = t2
            elif ev["score2"] > ev["score1"]:
                winner = "team2"
                ganadores[ko_num] = t2
                perdedores[ko_num] = t1

        partidos.append({
            "id": f"KO-{ko_num:03d}",
            "koNum": ko_num,
            "date": ev["date"],
            "team1": t1,
            "team2": t2,
            "status": status,
            "winner": winner,
            "side": spec["side"],
            "order": spec["order"],
            "round": spec["round"],
        })

    # Agrupar por ronda y ordenar por 'order' (lado izquierdo y derecho intercalados,
    # el filtro por 'side' en el front conserva el orden relativo de cada mitad)
    rounds = {
        "round_of_32": [], "round_of_16": [], "quarter_finals": [],
        "semi_finals": [], "third_place": None, "final": None,
    }
    for p in partidos:
        r = p["round"]
        if r in ("third_place", "final"):
            rounds[r] = p
        else:
            rounds[r].append(p)
    for r in ("round_of_32", "round_of_16", "quarter_finals", "semi_finals"):
        rounds[r].sort(key=lambda x: (x["order"], 0 if x["side"] == "left" else 1))

    champion = None
    final_match = rounds.get("final")
    if final_match and final_match["winner"]:
        champion = final_match["team1"] if final_match["winner"] == "team1" else final_match["team2"]

    bracket_data = {
        "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "rounds": rounds,
        "champion": champion,
        "groups": tablas,
        "bestThirds": tabla_terceros,
        "fixtures": fixtures,
    }

    with open('bracket_data.json', 'w', encoding='utf-8') as f:
        json.dump(bracket_data, f, ensure_ascii=False, indent=2)

    finalizados = sum(1 for p in partidos if p["status"] == "finished")
    con_equipos = sum(1 for p in partidos
                      if not p["team1"].get("placeholder") and not p["team2"].get("placeholder"))
    grupos_completos = sum(1 for g in tablas.values() if g["complete"])
    print("\n✅ bracket_data.json generado:")
    print(f"   🏆 {len(partidos)} cruces ({finalizados} finalizados, "
          f"{con_equipos} con ambos equipos definidos)")
    print(f"   📊 {grupos_completos}/{len(tablas)} grupos completos")


if __name__ == "__main__":
    generar_bracket()
