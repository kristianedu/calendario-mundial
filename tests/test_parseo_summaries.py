"""Tests de las funciones puras de parseo de generar_bracket.py."""
from datetime import datetime

import pytest

from generar_bracket import (
    parsear_equipo_del_summary,
    parsear_resultado_grupo,
    extraer_grupo,
    formatear_fecha,
    etiqueta_corta,
)


class TestParsearEquipoDelSummary:
    def test_partido_pendiente_vs(self):
        r = parsear_equipo_del_summary(
            "🏆 🇫🇷 Francia vs Suecia 🇸🇪 - Treintaidosavos de Final")
        assert r["team1"] == "Francia"
        assert r["team2"] == "Suecia"
        assert r["score1"] is None and r["score2"] is None
        assert r["status"] == "pending"

    def test_partido_finalizado_con_marcador(self):
        r = parsear_equipo_del_summary(
            "✅ 🇧🇷 Brasil [2] - [1] Japón 🇯🇵 - Treintaidosavos de Final (Final)")
        assert r["team1"] == "Brasil"
        assert r["team2"] == "Japón"
        assert (r["score1"], r["score2"]) == (2, 1)
        assert r["status"] == "finished"
        assert r["pen1"] is None and r["pen2"] is None

    def test_partido_en_vivo(self):
        r = parsear_equipo_del_summary(
            "🔴 🇲🇽 México [1] - [0] Ecuador 🇪🇨 - Treintaidosavos de Final (En Vivo)")
        assert r["status"] == "live"
        assert (r["score1"], r["score2"]) == (1, 0)

    @pytest.mark.parametrize("etapa", ["(Medio Tiempo)", "(Tiempo Extra)", "(Penales)"])
    def test_otros_estados_en_vivo(self, etapa):
        r = parsear_equipo_del_summary(
            f"🔴 🇲🇽 México [0] - [0] Ecuador 🇪🇨 - Octavos de Final {etapa}")
        assert r["status"] == "live"

    def test_definido_por_penales(self):
        r = parsear_equipo_del_summary(
            "✅ 🇦🇷 Argentina [1] - [1] Países Bajos 🇳🇱 - "
            "Cuartos de Final (Final) [Penales: 4-3]")
        assert (r["score1"], r["score2"]) == (1, 1)
        assert (r["pen1"], r["pen2"]) == (4, 3)
        assert r["status"] == "finished"

    def test_equipo_multipalabra(self):
        r = parsear_equipo_del_summary(
            "✅ 🇸🇦 Arabia Saudita [0] - [3] Corea del Sur 🇰🇷 - Grupo A (Final)")
        assert r["team1"] == "Arabia Saudita"
        assert r["team2"] == "Corea del Sur"

    def test_bandera_inglaterra_secuencia_de_tags(self):
        # La bandera de Inglaterra (🏴 + tags) usa la rama alternativa del regex.
        r = parsear_equipo_del_summary(
            "🏆 🏴\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F "
            "Inglaterra vs Senegal 🇸🇳 - Treintaidosavos de Final")
        assert r["team1"] == "Inglaterra"
        assert r["team2"] == "Senegal"

    def test_summary_sin_banderas_no_extrae_equipos(self):
        r = parsear_equipo_del_summary("⚽ México vs Sudáfrica - Grupo A")
        assert r["team1"] is None and r["team2"] is None
        assert r["status"] == "pending"

    def test_cruce_sin_equipos_definidos(self):
        r = parsear_equipo_del_summary("🏆 Octavos de Final: 1°E vs 3° - Por definir")
        assert r["team1"] is None and r["team2"] is None


class TestParsearResultadoGrupo:
    def test_finalizado_con_marcador(self):
        r = parsear_resultado_grupo(
            "✅ 🇲🇽 México [2] - [0] Sudáfrica 🇿🇦 - Grupo A (Final)")
        assert r == ("México", "Sudáfrica", 2, 0, True)

    def test_pendiente_vs(self):
        r = parsear_resultado_grupo("⚽ 🇪🇸 España vs Alemania 🇩🇪 - Grupo E")
        assert r == ("España", "Alemania", None, None, False)

    def test_texto_no_parseable_devuelve_none(self):
        assert parsear_resultado_grupo("Partido por definir") is None


class TestExtraerGrupo:
    def test_grupo_en_descripcion(self):
        assert extraer_grupo(
            "Copa Mundial FIFA 2026\nFase de Grupos - Grupo A - Jornada 1") == "A"
        assert extraer_grupo("... Grupo L - Jornada 3") == "L"

    def test_sin_grupo(self):
        assert extraer_grupo("Fase Eliminatoria - Octavos de Final") is None


class TestFormatearFecha:
    def test_fecha_en_espanol(self):
        assert formatear_fecha(datetime(2026, 6, 28)) == "28 jun"
        assert formatear_fecha(datetime(2026, 7, 19)) == "19 jul"
        assert formatear_fecha(datetime(2026, 12, 1)) == "1 dic"


class TestEtiquetaCorta:
    @pytest.mark.parametrize("ko,esperado", [
        (1, "T1"), (16, "T16"),     # Treintaidosavos
        (17, "O1"), (24, "O8"),     # Octavos
        (25, "C1"), (28, "C4"),     # Cuartos
        (29, "S1"), (30, "S2"),     # Semifinales
        (31, "P31"), (32, "P32"),   # 3er lugar y Final (genérico)
    ])
    def test_etiquetas(self, ko, esperado):
        assert etiqueta_corta(ko) == esperado
