"""
Tests de generar_bracket.py contra un .ics mínimo (tests/fixtures/mini_mundial.ics).

El fixture define:
  - Grupos A, B, C y F con 2 equipos y 1 partido jugado (proyecta 1º y 2º).
  - Grupo G con 4 equipos y 2 partidos (ejercita el desempate por diferencia de gol).
  - KO-001 (2A vs 2B): Sudáfrica 1-1 Qatar, definido por penales 4-2.
  - KO-003 (1F vs 2C): en el .ics aparece como "Ghana 0-2 Francia", INVERTIDO
    respecto al orden del cuadro (t1=Francia), para probar la reorientación.
  - KO-004 (1C vs 2F): Inglaterra vs Senegal, pendiente.
  - KO-018 (G·T1 vs G·T3): pendiente; debe poblarse con los ganadores propagados.
"""
import json
import shutil

import pytest

import generar_bracket as gb


# ═══════════════════════════════════════════════════════════════════
#  Tablas de grupos
# ═══════════════════════════════════════════════════════════════════
class TestTablasGrupos:
    def test_grupos_detectados(self, mini_cal):
        tablas = gb.calcular_tablas_grupos(mini_cal)
        assert set(tablas.keys()) == {"A", "B", "C", "F", "G"}

    def test_estadisticas_grupo_a(self, mini_cal):
        tablas = gb.calcular_tablas_grupos(mini_cal)
        equipos = tablas["A"]["teams"]
        assert [e["fullName"] for e in equipos] == ["México", "Sudáfrica"]
        mex, rsa = equipos
        assert (mex["pts"], mex["pj"], mex["pg"], mex["gf"], mex["gc"], mex["dg"]) == \
            (3, 1, 1, 2, 0, 2)
        assert (rsa["pts"], rsa["pp"], rsa["dg"]) == (0, 1, -2)
        assert mex["name"] == "MEX" and mex["flag"] == "🇲🇽"

    def test_desempate_por_diferencia_de_gol(self, mini_cal):
        # Grupo G: Bélgica 3-1 Egipto y Croacia 1-0 Uruguay.
        # Bélgica y Croacia tienen 3 pts; Bélgica va primero por dg (+2 vs +1).
        tablas = gb.calcular_tablas_grupos(mini_cal)
        orden = [e["fullName"] for e in tablas["G"]["teams"]]
        assert orden == ["Bélgica", "Croacia", "Uruguay", "Egipto"]

    def test_posiciones_y_status(self, mini_cal):
        tablas = gb.calcular_tablas_grupos(mini_cal)
        g = tablas["G"]["teams"]
        assert [e["pos"] for e in g] == [1, 2, 3, 4]
        assert g[0]["status"] == "qualified"
        assert g[1]["status"] == "qualified"
        assert g[2]["status"] == "possible"
        # Nadie está eliminado matemáticamente con 2 partidos por jugar.
        assert not any(e["eliminated"] for e in g)

    def test_grupo_completo_cuando_todo_jugado(self, mini_cal):
        tablas = gb.calcular_tablas_grupos(mini_cal)
        # Todos los partidos listados del grupo A están finalizados.
        assert tablas["A"]["complete"] is True
        assert tablas["A"]["played"] == tablas["A"]["total"] == 1


# ═══════════════════════════════════════════════════════════════════
#  Lectura de eventos KO y pool de resultados
# ═══════════════════════════════════════════════════════════════════
class TestEventosKO:
    def test_leer_eventos_ko(self, mini_cal):
        eventos = gb.leer_eventos_ko(mini_cal)
        assert set(eventos.keys()) == {1, 3, 4, 18}

        ev1 = eventos[1]
        assert (ev1["team1"], ev1["team2"]) == ("Sudáfrica", "Qatar")
        assert (ev1["score1"], ev1["score2"]) == (1, 1)
        assert (ev1["pen1"], ev1["pen2"]) == (4, 2)
        assert ev1["status"] == "finished"
        assert ev1["date"] == "28 jun"

        ev4 = eventos[4]
        assert (ev4["team1"], ev4["team2"]) == ("Inglaterra", "Senegal")
        assert ev4["status"] == "pending"
        assert ev4["score1"] is None

    def test_pool_indexado_por_par_de_equipos(self, mini_cal):
        pool = gb.construir_pool_resultados(gb.leer_eventos_ko(mini_cal))
        assert frozenset({"Sudáfrica", "Qatar"}) in pool
        assert frozenset({"Ghana", "Francia"}) in pool
        # La clave es simétrica: no importa el orden de los equipos.
        assert pool[frozenset({"Qatar", "Sudáfrica"})]["pen1"] == 4


# ═══════════════════════════════════════════════════════════════════
#  Proyección y propagación de ganadores
# ═══════════════════════════════════════════════════════════════════
class TestProyeccion:
    def test_proyeccion_desde_posiciones_de_grupo(self, mini_cal):
        proy = gb.proyectar_equipos_ko(mini_cal)
        assert proy[1] == ("Sudáfrica", "Qatar")        # 2A vs 2B
        assert proy[3] == ("Francia", "Ghana")          # 1F vs 2C (orden del cuadro)
        assert proy[4] == ("Inglaterra", "Senegal")     # 1C vs 2F

    def test_slot_sin_grupo_queda_indefinido(self, mini_cal):
        proy = gb.proyectar_equipos_ko(mini_cal)
        assert proy[11] == (None, None)                 # 2K vs 2L: grupos sin datos
        assert proy[16] == (None, "Croacia")            # 2D vs 2G: solo hay grupo G

    def test_propagacion_de_ganadores_a_octavos(self, mini_cal):
        # KO-018 = ganador KO-001 vs ganador KO-003.
        # KO-001 se definió por penales (Sudáfrica) y KO-003 en los 90' (Francia).
        proy = gb.proyectar_equipos_ko(mini_cal)
        assert proy[18] == ("Sudáfrica", "Francia")

    def test_rondas_posteriores_sin_definir(self, mini_cal):
        proy = gb.proyectar_equipos_ko(mini_cal)
        assert proy[25] == (None, None)                 # cuartos
        assert proy[32] == (None, None)                 # final


# ═══════════════════════════════════════════════════════════════════
#  Generación completa del bracket_data.json con el fixture
# ═══════════════════════════════════════════════════════════════════
@pytest.fixture
def bracket_data_mini(tmp_path, monkeypatch, mini_ics_path):
    """Ejecuta generar_bracket() en un tmpdir con el .ics mínimo."""
    shutil.copy(mini_ics_path, tmp_path / "base_mundial.ics")
    monkeypatch.chdir(tmp_path)
    gb.generar_bracket()
    with open(tmp_path / "bracket_data.json", encoding="utf-8") as f:
        return json.load(f)


def _match(data, ko_num):
    ronda = gb.BRACKET[ko_num]["round"]
    partidos = data["rounds"][ronda]
    if isinstance(partidos, dict):
        return partidos
    return next(p for p in partidos if p["koNum"] == ko_num)


class TestGeneracionCompletaMini:
    def test_estructura_de_rondas(self, bracket_data_mini):
        rounds = bracket_data_mini["rounds"]
        assert len(rounds["round_of_32"]) == 16
        assert len(rounds["round_of_16"]) == 8
        assert len(rounds["quarter_finals"]) == 4
        assert len(rounds["semi_finals"]) == 2
        assert isinstance(rounds["third_place"], dict)
        assert isinstance(rounds["final"], dict)

    def test_cruce_definido_por_penales(self, bracket_data_mini):
        p = _match(bracket_data_mini, 1)
        assert p["status"] == "finished"
        assert p["team1"]["fullName"] == "Sudáfrica"
        assert p["team2"]["fullName"] == "Qatar"
        assert (p["team1"]["score"], p["team2"]["score"]) == (1, 1)
        assert (p["team1"]["pen"], p["team2"]["pen"]) == (4, 2)
        # Empate 1-1: gana team1 por penales 4-2.
        assert p["winner"] == "team1"

    def test_marcador_reorientado_al_orden_del_cuadro(self, bracket_data_mini):
        # El .ics tiene "Ghana [0] - [2] Francia" pero el cuadro proyecta
        # t1=Francia (1F), t2=Ghana (2C): el marcador debe voltearse.
        p = _match(bracket_data_mini, 3)
        assert p["team1"]["fullName"] == "Francia"
        assert p["team2"]["fullName"] == "Ghana"
        assert (p["team1"]["score"], p["team2"]["score"]) == (2, 0)
        assert p["winner"] == "team1"
        assert p["status"] == "finished"

    def test_cruce_pendiente_con_equipos_reales(self, bracket_data_mini):
        p = _match(bracket_data_mini, 4)
        assert p["status"] == "pending"
        assert p["winner"] is None
        assert p["team1"]["fullName"] == "Inglaterra"
        assert p["team2"]["fullName"] == "Senegal"
        assert p["team1"]["placeholder"] is False
        assert p["date"] == "30 jun"

    def test_ganadores_propagados_a_octavos(self, bracket_data_mini):
        p = _match(bracket_data_mini, 18)
        assert p["team1"]["fullName"] == "Sudáfrica"    # ganó KO-001 por penales
        assert p["team2"]["fullName"] == "Francia"      # ganó KO-003
        assert not p["team1"]["placeholder"]
        assert not p["team2"]["placeholder"]
        assert p["status"] == "pending"
        assert p["date"] == "4 jul"

    def test_cruce_sin_definir_usa_placeholders(self, bracket_data_mini):
        p = _match(bracket_data_mini, 17)   # ganador KO-002 vs ganador KO-005
        assert p["team1"]["placeholder"] is True
        assert p["team1"]["name"] == "G·T2"
        assert p["team2"]["name"] == "G·T5"
        assert p["team1"]["flag"] == "🛡️"

    def test_final_y_campeon_sin_definir(self, bracket_data_mini):
        final = bracket_data_mini["rounds"]["final"]
        assert final["id"] == "KO-032"
        assert final["team1"]["placeholder"] and final["team2"]["placeholder"]
        assert bracket_data_mini["champion"] is None

    def test_topologia_de_avance_incluida(self, bracket_data_mini):
        p = _match(bracket_data_mini, 1)
        assert p["winnerTo"] == {"ko": 18, "slot": "team1"}
        assert p["loserTo"] is None
        semi1 = _match(bracket_data_mini, 29)
        assert semi1["winnerTo"] == {"ko": 32, "slot": "team1"}
        assert semi1["loserTo"] == {"ko": 31, "slot": "team1"}

    def test_tabla_de_terceros(self, bracket_data_mini):
        # Solo el grupo G tiene 3+ equipos: su tercero (Uruguay) es el único
        # candidato y queda entre los mejores terceros.
        filas = bracket_data_mini["bestThirds"]
        assert len(filas) == 1
        assert filas[0]["fullName"] == "Uruguay"
        assert filas[0]["group"] == "G"
        assert filas[0]["qualified"] is True

    def test_fixtures_recientes_y_proximos(self, bracket_data_mini):
        fixtures = bracket_data_mini["fixtures"]
        recientes = fixtures["recent"]
        proximos = fixtures["upcoming"]
        assert all(e["status"] == "finished" for e in recientes)
        assert all(e["status"] != "finished" for e in proximos)
        # 6 de grupos + KO-001 y KO-003 finalizados = 8 (justo el tope).
        assert len(recientes) == 8
        # KO-004 y KO-018 pendientes, ordenados por fecha.
        assert [e["team1"]["fullName"] for e in proximos] == ["Inglaterra", "Sudáfrica"]
