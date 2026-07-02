"""Configuración compartida de pytest para el repo partidos."""
import os
import sys

import pytest

# Permitir `import equipos` / `import generar_bracket` desde la raíz del repo.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


@pytest.fixture
def repo_root():
    """Ruta absoluta a la raíz del repo."""
    return REPO_ROOT


@pytest.fixture
def mini_ics_path():
    """Ruta al calendario .ics mínimo de pruebas."""
    return os.path.join(FIXTURES_DIR, "mini_mundial.ics")


@pytest.fixture
def mini_cal(mini_ics_path):
    """Calendario icalendar ya parseado del fixture mínimo."""
    from icalendar import Calendar
    with open(mini_ics_path, "rb") as f:
        return Calendar.from_ical(f.read())
