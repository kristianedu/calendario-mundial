"""Tests de la estructura estática del cuadro FIFA 2026 (dict BRACKET)."""
from collections import Counter

from generar_bracket import BRACKET, ADVANCES, THIRD_SLOTS, THIRD_SLOT_WINNER


def test_bracket_tiene_32_cruces_ko_1_a_32():
    assert set(BRACKET.keys()) == set(range(1, 33))


def test_cantidad_de_cruces_por_ronda():
    rondas = Counter(spec["round"] for spec in BRACKET.values())
    assert rondas == {
        "round_of_32": 16,
        "round_of_16": 8,
        "quarter_finals": 4,
        "semi_finals": 2,
        "third_place": 1,
        "final": 1,
    }


def test_hay_8_slots_de_mejores_terceros():
    assert len(THIRD_SLOTS) == 8
    # Cada slot de tercero permite 5 grupos según el cuadro oficial FIFA.
    for grupos in THIRD_SLOTS.values():
        assert len(grupos) == 5
        assert all(g in "ABCDEFGHIJKL" for g in grupos)


def test_third_slot_winner_apunta_a_ganadores_de_grupo():
    # Cada slot de tercero enfrenta a un 1º de grupo (t1 = ('pos', '1X')).
    assert set(THIRD_SLOT_WINNER.keys()) == set(THIRD_SLOTS.keys())
    for ko, grupo in THIRD_SLOT_WINNER.items():
        assert BRACKET[ko]["t1"] == ("pos", f"1{grupo}")


def test_referencias_de_ganadores_y_perdedores_validas():
    for ko, spec in BRACKET.items():
        for kind, val in (spec["t1"], spec["t2"]):
            if kind in ("w", "l"):
                assert val in BRACKET, f"KO-{ko} referencia cruce inexistente {val}"
                assert val < ko, f"KO-{ko} depende de un cruce posterior ({val})"


def test_cada_ganador_de_r32_a_semis_avanza_a_un_unico_slot():
    # Todo cruce salvo 3er lugar y final debe alimentar exactamente un slot.
    for ko in range(1, 31):
        assert "winnerTo" in ADVANCES[ko], f"KO-{ko} no tiene destino de ganador"
    # 3er lugar y final no alimentan a nadie.
    assert 31 not in ADVANCES
    assert 32 not in ADVANCES


def test_semifinales_alimentan_final_y_tercer_lugar():
    assert ADVANCES[29]["winnerTo"] == {"ko": 32, "slot": "team1"}
    assert ADVANCES[30]["winnerTo"] == {"ko": 32, "slot": "team2"}
    assert ADVANCES[29]["loserTo"] == {"ko": 31, "slot": "team1"}
    assert ADVANCES[30]["loserTo"] == {"ko": 31, "slot": "team2"}


def test_solo_semifinales_tienen_destino_de_perdedor():
    con_loser = {ko for ko, dest in ADVANCES.items() if "loserTo" in dest}
    assert con_loser == {29, 30}


def test_posiciones_de_grupo_cubren_los_12_grupos():
    # En treintaidosavos deben aparecer los 12 primeros y los 12 segundos
    # de grupo (los segundos entran todos; 8 terceros ocupan el resto).
    posiciones = [val for spec in BRACKET.values()
                  for kind, val in (spec["t1"], spec["t2"]) if kind == "pos"]
    primeros = {p[1] for p in posiciones if p.startswith("1")}
    segundos = {p[1] for p in posiciones if p.startswith("2")}
    assert primeros == set("ABCDEFGHIJKL")
    assert segundos == set("ABCDEFGHIJKL")
    assert len(posiciones) == 24
