def hhmm_to_min(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def min_to_hhmm(total: int) -> str:
    total = max(0, int(total))
    return f"{total // 60:02d}:{total % 60:02d}"
