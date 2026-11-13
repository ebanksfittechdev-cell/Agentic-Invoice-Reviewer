from decimal import Decimal


def verify_total(lines: list[dict], stated_total: float | None) -> bool:
    """Return True if the sum of line_total values matches stated_total within $0.01."""
    if stated_total is None:
        return False
    computed = sum(Decimal(str(line.get("line_total") or 0)) for line in lines)
    return abs(computed - Decimal(str(stated_total))) <= Decimal("0.01")
