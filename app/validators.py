"""Brazilian document validators (CPF, CNPJ, postal code, phone).

Written by hand rather than pulled from a library: the check-digit rules are a
dozen lines each and are worth reading, and a dependency here would be a
dependency in the critical path of every signup.
"""

import re

_NON_DIGITS = re.compile(r"\D")


def digits_only(value: str | None) -> str:
    return _NON_DIGITS.sub("", value or "")


def is_valid_cpf(cpf: str) -> bool:
    """CPF is the Brazilian individual taxpayer number: 11 digits, the last
    two being check digits computed from the first nine."""
    cpf = digits_only(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for length in (9, 10):
        total = sum(int(cpf[i]) * (length + 1 - i) for i in range(length))
        check = (total * 10) % 11 % 10
        if check != int(cpf[length]):
            return False
    return True


def is_valid_cnpj(cnpj: str) -> bool:
    """CNPJ is the Brazilian company registration number: 14 digits with two
    check digits, using a different weight sequence from the CPF."""
    cnpj = digits_only(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    weights_first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights_second = [6] + weights_first
    for weights, position in ((weights_first, 12), (weights_second, 13)):
        total = sum(int(cnpj[i]) * weights[i] for i in range(position))
        remainder = total % 11
        check = 0 if remainder < 2 else 11 - remainder
        if check != int(cnpj[position]):
            return False
    return True


def is_valid_postal_code(code: str) -> bool:
    return len(digits_only(code)) == 8


def is_valid_phone(phone: str) -> bool:
    """Accepts landline (10 digits) or mobile (11), area code included."""
    return len(digits_only(phone)) in (10, 11)


def format_cpf(cpf: str) -> str:
    d = digits_only(cpf)
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else cpf


def format_cnpj(cnpj: str) -> str:
    d = digits_only(cnpj)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else cnpj
