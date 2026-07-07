"""Tests del guard contra finales prematuros de la API en generador.py.

Un cruce eliminatorio no puede terminar empatado sin tanda de penales;
si la API reporta FINISHED así (final prematuro o marcador stale, como
Portugal-Croacia en treintaidosavos 2026), no debe congelarse como (Final).
"""
from generador import final_sospechoso


def test_empate_sin_penales_en_eliminatorias_es_sospechoso():
    assert final_sospechoso(True, 2, 2, None, None) is True


def test_empate_con_penales_parciales_es_sospechoso():
    # Penales incompletos (solo un lado reportado) tampoco definen ganador
    assert final_sospechoso(True, 1, 1, 4, None) is True
    assert final_sospechoso(True, 1, 1, None, 2) is True


def test_empate_con_penales_completos_no_es_sospechoso():
    assert final_sospechoso(True, 2, 2, 4, 2) is False


def test_empate_con_penales_empatados_es_sospechoso():
    # Una tanda de penales no puede terminar empatada: la API marcó FINISHED
    # a mitad de la tanda (Suiza-Colombia 1-1 [Penales: 1-1], octavos 2026)
    assert final_sospechoso(True, 1, 1, 1, 1) is True
    assert final_sospechoso(True, 0, 0, 0, 0) is True


def test_victoria_en_eliminatorias_no_es_sospechosa():
    assert final_sospechoso(True, 2, 1, None, None) is False


def test_empate_en_fase_de_grupos_no_es_sospechoso():
    # En grupos el empate es un resultado final válido
    assert final_sospechoso(False, 0, 0, None, None) is False


def test_penales_cero_cuenta_como_dato_presente():
    # Un 0 en la tanda es un dato real, no ausencia de dato
    assert final_sospechoso(True, 1, 1, 3, 0) is False
