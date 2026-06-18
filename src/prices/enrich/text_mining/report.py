_NO_ROWS = "_(no rows)_"


def _cell(value) -> str:
    if value is None:
        return ""
    return str(value)


def md_table(rows: list[dict], columns: list[str] | None = None) -> str:
    if not rows:
        return _NO_ROWS
    cols = columns if columns is not None else list(rows[0].keys())
    header = "| " + " | ".join(cols) + " |"
    separator = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(_cell(row.get(c)) for c in cols) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def md_section(title: str, level: int = 2) -> str:
    level = max(1, min(level, 6))
    return ("#" * level) + " " + title


def md_slice_block(
    title: str,
    slices: dict[tuple, list[dict]],
    level: int = 2,
    columns: list[str] | None = None,
) -> str:
    parts = [md_section(title, level)]
    for key, rows in slices.items():
        if isinstance(key, tuple):
            sub_title = " × ".join(_cell(k) for k in key)
        else:
            sub_title = _cell(key)
        parts.append(md_section(sub_title, level + 1))
        parts.append(md_table(rows, columns=columns))
    return "\n\n".join(parts)
