"""Tests para routes_csv.py — parsing del CSV de intenciones."""

from __future__ import annotations

import pytest
from pathlib import Path

from ruteador_semantico.routes_csv import routes_from_intents_csv


def _write_csv(tmp_path: Path, content: str, encoding: str = "utf-8") -> Path:
    p = tmp_path / "intents.csv"
    p.write_text(content, encoding=encoding)
    return p


# ---------------------------------------------------------------------------
# Parsing básico
# ---------------------------------------------------------------------------

def test_single_category(tmp_path):
    p = _write_csv(tmp_path, "1,HOLA,SALUDO\n2,BUEN DÍA,SALUDO\n")
    routes = routes_from_intents_csv(p)
    assert len(routes) == 1
    assert routes[0].name == "SALUDO"
    assert set(routes[0].utterances) == {"HOLA", "BUEN DÍA"}


def test_multiple_categories(tmp_path):
    p = _write_csv(tmp_path, "1,HOLA,SALUDO\n2,CHAU,DESPEDIDA\n3,ABL,TRAMITES\n")
    routes = routes_from_intents_csv(p)
    names = {r.name for r in routes}
    assert names == {"SALUDO", "DESPEDIDA", "TRAMITES"}


def test_result_sorted_alphabetically(tmp_path):
    p = _write_csv(tmp_path, "1,BACHE,RECLAMOS\n2,HOLA,SALUDO\n3,ABL,TRAMITES\n")
    routes = routes_from_intents_csv(p)
    assert [r.name for r in routes] == ["RECLAMOS", "SALUDO", "TRAMITES"]


def test_utterances_grouped_by_category(tmp_path):
    content = "1,HOLA,SALUDO\n2,BUEN DÍA,SALUDO\n3,QUÉ TAL,SALUDO\n"
    p = _write_csv(tmp_path, content)
    routes = routes_from_intents_csv(p)
    assert len(routes) == 1
    assert len(routes[0].utterances) == 3


# ---------------------------------------------------------------------------
# Filas inválidas o vacías
# ---------------------------------------------------------------------------

def test_skips_row_with_empty_utterance(tmp_path):
    p = _write_csv(tmp_path, "1,,SALUDO\n2,HOLA,SALUDO\n")
    routes = routes_from_intents_csv(p)
    assert routes[0].utterances == ["HOLA"]


def test_skips_row_with_empty_category(tmp_path):
    p = _write_csv(tmp_path, "1,HOLA,\n2,CHAU,DESPEDIDA\n")
    routes = routes_from_intents_csv(p)
    names = {r.name for r in routes}
    assert "DESPEDIDA" in names
    assert "" not in names


def test_skips_row_with_too_few_columns(tmp_path):
    p = _write_csv(tmp_path, "1,HOLA\n2,BUEN DÍA,SALUDO\n")
    routes = routes_from_intents_csv(p)
    assert len(routes) == 1
    assert routes[0].name == "SALUDO"


def test_empty_csv_returns_empty_list(tmp_path):
    p = _write_csv(tmp_path, "")
    routes = routes_from_intents_csv(p)
    assert routes == []


def test_all_rows_invalid_returns_empty_list(tmp_path):
    p = _write_csv(tmp_path, "1,\n2,SOLO_DOS\n")
    routes = routes_from_intents_csv(p)
    assert routes == []


# ---------------------------------------------------------------------------
# Manejo de caracteres especiales y encoding
# ---------------------------------------------------------------------------

def test_quoted_utterance_with_comma(tmp_path):
    # CSV estándar: campo entre comillas puede contener comas
    p = _write_csv(tmp_path, '9,"ME DUELE LA CABEZA, ¿DÓNDE ME ATIENDO?",SALUD\n')
    routes = routes_from_intents_csv(p)
    assert len(routes) == 1
    assert "ME DUELE LA CABEZA, ¿DÓNDE ME ATIENDO?" in routes[0].utterances


def test_utf8_bom_handling(tmp_path):
    """Archivo guardado con BOM (común en Excel/Windows) debe parsearse correctamente."""
    p = tmp_path / "intents.csv"
    # Escribir con BOM UTF-8
    p.write_bytes(b"\xef\xbb\xbf1,HOLA,SALUDO\n2,CHAU,DESPEDIDA\n")
    routes = routes_from_intents_csv(p)
    names = {r.name for r in routes}
    assert names == {"SALUDO", "DESPEDIDA"}
    # La fila "1" del ID no debe quedar pegada al utterance
    assert "HOLA" in routes[next(i for i, r in enumerate(routes) if r.name == "SALUDO")].utterances


def test_accented_characters(tmp_path):
    content = "1,ÁRBOL CAÍDO EN LA CALLE,RECLAMOS\n2,ÑOQUERÍAS BARRIALES,CULTURA\n"
    p = _write_csv(tmp_path, content)
    routes = routes_from_intents_csv(p)
    names = {r.name for r in routes}
    assert names == {"RECLAMOS", "CULTURA"}


# ---------------------------------------------------------------------------
# CSV real del proyecto
# ---------------------------------------------------------------------------

def test_real_intents_csv():
    """El CSV de producción debe generar exactamente 9 rutas sin errores."""
    csv_path = Path(__file__).resolve().parent.parent / "Test" / "intents.csv"
    if not csv_path.is_file():
        pytest.skip("Test/intents.csv no encontrado")
    routes = routes_from_intents_csv(csv_path)
    names = {r.name for r in routes}
    expected = {
        "SALUD", "TRAMITES", "RECLAMOS", "DEPORTE",
        "CULTURA", "GENERAL", "SALUDO", "DESPEDIDA", "INEXISTENTE",
    }
    assert names == expected
    for r in routes:
        assert len(r.utterances) >= 1, f"Ruta {r.name} sin utterances"
