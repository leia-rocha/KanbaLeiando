"""Testes de fractional indexing (RF16)."""

from __future__ import annotations

from app.utils.sortkey import between, initial_key, is_valid


def test_between_none_none():
    k = between(None, None)
    assert is_valid(k)


def test_between_mantem_ordem():
    a = initial_key()
    b = between(a, None)
    assert b > a
    c = between(None, a)
    assert c < a


def test_insercao_no_meio_repetida():
    low = between(None, None)
    high = between(low, None)
    assert low < high
    for _ in range(50):
        mid = between(low, high)
        assert low < mid < high, (low, mid, high)
        high = mid  # vai apertando o espaco entre low e high


def test_sequencia_de_appends_fica_ordenada():
    keys = []
    prev = None
    for _ in range(100):
        k = between(prev, None)
        if keys:
            assert k > keys[-1]
        keys.append(k)
        prev = k
    assert keys == sorted(keys)


def test_prepend_repetido_fica_ordenado():
    keys = []
    first = None
    for _ in range(100):
        k = between(None, first)
        if keys:
            assert k < keys[-1]
        keys.append(k)
        first = k
    assert keys == sorted(keys, reverse=True)


def test_insercao_intensa_entre_vizinhos():
    # Simula muitas insercoes no mesmo intervalo, como arrastar sempre para a
    # mesma posicao. Mantem invariante low < mid < high.
    lo = between(None, None)
    hi = between(lo, None)
    seen = {lo, hi}
    for _ in range(200):
        mid = between(lo, hi)
        assert lo < mid < hi, (lo, mid, hi)
        assert mid not in seen
        seen.add(mid)
        hi = mid
