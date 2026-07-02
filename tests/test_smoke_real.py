"""
Test de humo end-to-end: genera bracket_data.json a partir del
base_mundial.ics REAL del repo y valida la estructura del JSON.
"""
import json
import os
import shutil

import pytest

import generar_bracket as gb

REQUIRED_TEAM_KEYS = {"name", "flag", "fullName", "score", "placeholder"}
REQUIRED_MATCH_KEYS = {
    "id", "koNum", "date", "team1", "team2", "status", "winner",
    "side", "order", "round", "winnerTo", "loserTo",
}


@pytest.fixture(scope="module")
def bracket_data(tmp_path_factory):
    """Corre la generación completa contra el .ics real en un tmpdir."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ics_real = os.path.join(repo_root, "base_mundial.ics")
    assert os.path.exists(ics_real), "base_mundial.ics no existe en el repo"

    tmp = tmp_path_factory.mktemp("smoke")
    shutil.copy(ics_real, tmp / "base_mundial.ics")

    cwd = os.getcwd()
    os.chdir(tmp)
    try:
        gb.generar_bracket()
    finally:
        os.chdir(cwd)

    salida = tmp / "bracket_data.json"
    assert salida.exists(), "generar_bracket() no escribió bracket_data.json"
    with open(salida, encoding="utf-8") as f:
        return json.load(f)


def test_llaves_de_primer_nivel(bracket_data):
    assert set(bracket_data.keys()) == {
        "lastUpdated", "rounds", "champion", "groups", "bestThirds", "fixtures",
    }


def test_rondas_completas(bracket_data):
    rounds = bracket_data["rounds"]
    assert len(rounds["round_of_32"]) == 16
    assert len(rounds["round_of_16"]) == 8
    assert len(rounds["quarter_finals"]) == 4
    assert len(rounds["semi_finals"]) == 2
    assert isinstance(rounds["third_place"], dict)
    assert isinstance(rounds["final"], dict)
    # Los 16 cruces de treintaidosavos son KO-001..KO-016.
    assert {p["koNum"] for p in rounds["round_of_32"]} == set(range(1, 17))
    assert rounds["final"]["id"] == "KO-032"


def test_todos_los_partidos_bien_formados(bracket_data):
    rounds = bracket_data["rounds"]
    partidos = (rounds["round_of_32"] + rounds["round_of_16"]
                + rounds["quarter_finals"] + rounds["semi_finals"]
                + [rounds["third_place"], rounds["final"]])
    assert len(partidos) == 32
    for p in partidos:
        assert REQUIRED_MATCH_KEYS <= set(p.keys()), p["id"]
        assert p["status"] in ("pending", "live", "finished")
        assert p["winner"] in (None, "team1", "team2")
        for slot in ("team1", "team2"):
            assert REQUIRED_TEAM_KEYS <= set(p[slot].keys()), p["id"]


def test_partidos_finalizados_tienen_marcador_y_ganador(bracket_data):
    for p in bracket_data["rounds"]["round_of_32"]:
        if p["status"] == "finished":
            assert p["team1"]["score"] is not None
            assert p["team2"]["score"] is not None
            assert p["winner"] in ("team1", "team2")


def test_grupos_a_a_l(bracket_data):
    grupos = bracket_data["groups"]
    assert set(grupos.keys()) == set("ABCDEFGHIJKL")
    for letra, info in grupos.items():
        assert len(info["teams"]) == 4, f"Grupo {letra} sin 4 equipos"
        assert info["played"] <= info["total"]
        for eq in info["teams"]:
            # Todo equipo real de grupo debe estar mapeado (código y bandera).
            assert eq["name"] != "TBD", f"{eq['fullName']} sin código"
            assert eq["flag"] != "🏳️", f"{eq['fullName']} sin bandera"
            assert eq["pos"] in (1, 2, 3, 4)
            assert eq["status"] in ("qualified", "possible",
                                    "contention", "eliminated")
            assert eq["gf"] - eq["gc"] == eq["dg"]
            assert eq["pg"] + eq["pe"] + eq["pp"] == eq["pj"]


def test_tabla_de_mejores_terceros(bracket_data):
    filas = bracket_data["bestThirds"]
    assert len(filas) == 12
    clasificados = [f for f in filas if f["qualified"]]
    assert len(clasificados) == 8
    # Ordenada por posición 1..12.
    assert [f["pos"] for f in filas] == list(range(1, 13))


def test_fixtures_resumen(bracket_data):
    fixtures = bracket_data["fixtures"]
    assert set(fixtures.keys()) == {"recent", "upcoming"}
    assert len(fixtures["recent"]) <= 8
    assert len(fixtures["upcoming"]) <= 8
    for e in fixtures["recent"]:
        assert e["status"] == "finished"
        assert e["score1"] is not None and e["score2"] is not None


def test_champion_coherente(bracket_data):
    champion = bracket_data["champion"]
    final = bracket_data["rounds"]["final"]
    if final["winner"]:
        assert champion == final[final["winner"]]
    else:
        assert champion is None
