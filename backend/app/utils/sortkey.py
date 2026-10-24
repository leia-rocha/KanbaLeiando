"""Fractional indexing para ordenacao de colunas, cards, campos e itens (RF16).

Gera uma chave de ordenacao entre dois vizinhos sem renumerar todos os irmaos.
As chaves sao strings comparadas lexicograficamente. A posicao final e sempre
calculada no servidor a partir dos IDs reais dos vizinhos, nunca de um indice do
estado local do cliente.

Implementacao baseada no algoritmo de fractional indexing com base62.
"""

from __future__ import annotations

_BASE = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_RADIX = len(_BASE)


def _digit(s: str, i: int, default: int) -> int:
    return _BASE.index(s[i]) if i < len(s) else default


def _midpoint(a: str, b: str) -> str:
    """String estritamente entre a e b (a < b), ou apos a quando b vazio.

    a e b sao fracoes na base _RADIX (ponto implicito a esquerda). Constroi o
    resultado digito a digito, nunca terminando em zero de base.
    """
    if b and a >= b:
        raise ValueError(f"sortkey invalida: {a!r} nao e menor que {b!r}")

    result: list[str] = []
    i = 0
    while True:
        da = _digit(a, i, 0)
        # Quando b e vazio, o limite superior e _RADIX (fim do alfabeto).
        db = _digit(b, i, _RADIX) if b else _RADIX
        if da == db:
            # Digitos iguais: copia e avanca. (Com b vazio, da<_RADIX sempre.)
            result.append(_BASE[da])
            i += 1
            continue
        if db - da > 1:
            # Ha espaco: escolhe o digito do meio e termina.
            result.append(_BASE[(da + db) // 2])
            return "".join(result)
        # Digitos adjacentes (db == da + 1): copia da e continua um nivel abaixo,
        # agora com limite superior _RADIX ate encontrar folga.
        result.append(_BASE[da])
        i += 1
        # A partir daqui o limite superior passa a ser _RADIX (b "estourou").
        while True:
            da = _digit(a, i, 0)
            if da < _RADIX - 1:
                result.append(_BASE[(da + _RADIX) // 2])
                return "".join(result)
            result.append(_BASE[da])
            i += 1


def between(before: str | None, after: str | None) -> str:
    """Chave entre 'before' e 'after'. None representa inicio/fim da lista."""
    low = before or ""
    high = after or ""
    if low and high and low >= high:
        # Vizinhos fora de ordem: cai para insercao apos 'low'.
        high = ""
    if not low and not high:
        return _BASE[_RADIX // 2]
    return _midpoint(low, high)


def initial_key() -> str:
    """Primeira chave de uma lista vazia."""
    return _BASE[_RADIX // 2]


def is_valid(key: str) -> bool:
    return bool(key) and all(ch in _BASE for ch in key)
