"""Tests de equipos.py: normalización de nombres, banderas y códigos."""
from equipos import normalize_name, get_bandera, get_codigo


class TestNormalizeName:
    def test_nombre_mapeado_exacto(self):
        assert normalize_name("Mexico") == "México"
        assert normalize_name("Spain") == "España"
        assert normalize_name("Korea Republic") == "Corea del Sur"

    def test_alias_multiples_del_mismo_equipo(self):
        assert normalize_name("USA") == "EE.UU."
        assert normalize_name("United States") == "EE.UU."
        assert normalize_name("Czech Republic") == "Chequia"
        assert normalize_name("Czechia") == "Chequia"

    def test_fallback_insensible_a_mayusculas(self):
        # La API a veces devuelve "and" en minúscula, etc.
        assert normalize_name("Bosnia and Herzegovina") == "Bosnia y Herzegovina"
        assert normalize_name("MEXICO") == "México"
        assert normalize_name("usa") == "EE.UU."

    def test_variante_con_guion_de_la_api(self):
        # football-data.org reporta "Bosnia-Herzegovina" con guion; sin este
        # mapeo el cruce EE.UU.-Bosnia de treintaidosavos 2026 no registró.
        assert normalize_name("Bosnia-Herzegovina") == "Bosnia y Herzegovina"
        assert normalize_name("bosnia-herzegovina") == "Bosnia y Herzegovina"

    def test_nombre_desconocido_pasa_sin_cambios(self):
        assert normalize_name("Wakanda") == "Wakanda"
        assert normalize_name("Atlántida FC") == "Atlántida FC"

    def test_nombre_ya_en_espanol_no_mapeado_pasa_igual(self):
        # "Uruguay"/"Portugal" son iguales en ambos idiomas y están mapeados.
        assert normalize_name("Uruguay") == "Uruguay"
        assert normalize_name("Portugal") == "Portugal"


class TestGetBandera:
    def test_equipo_conocido(self):
        assert get_bandera("Argentina") == "🇦🇷"
        assert get_bandera("México") == "🇲🇽"

    def test_bandera_inglaterra_secuencia_regional(self):
        # Inglaterra usa la secuencia de tags 🏴 + gbeng, no un flag de 2 letras.
        bandera = get_bandera("Inglaterra")
        assert bandera.startswith("🏴")
        assert len(bandera) > 1

    def test_fallback_bandera_blanca(self):
        assert get_bandera("Wakanda") == "🏳️"
        assert get_bandera("") == "🏳️"


class TestGetCodigo:
    def test_equipo_conocido(self):
        assert get_codigo("Brasil") == "BRA"
        assert get_codigo("EE.UU.") == "USA"
        assert get_codigo("Arabia Saudita") == "KSA"

    def test_fallback_tbd(self):
        assert get_codigo("Wakanda") == "TBD"
        assert get_codigo("") == "TBD"

    def test_codigo_usa_nombre_espanol_no_ingles(self):
        # El mapa de códigos está indexado por el nombre en español.
        assert get_codigo("Mexico") == "TBD"
        assert get_codigo("México") == "MEX"
