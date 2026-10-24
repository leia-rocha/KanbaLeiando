"""Testes de normalizacao de texto (DT12, RF31, RF26)."""

from __future__ import annotations

from app.utils.text import normalize_email, normalize_name, normalize_search


def test_busca_ignora_acento_e_caixa():
    assert normalize_search("Produção") == normalize_search("producao")
    assert normalize_search("  Reunião   Final ") == "reuniao final"


def test_nome_de_modelo_normaliza_espacos_e_caixa():
    assert normalize_name("  Meu   Modelo ") == normalize_name("meu modelo")


def test_email_normaliza_caixa():
    assert normalize_email("  User@Example.COM ") == "user@example.com"
