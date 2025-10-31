import re
import unicodedata

_dashes_re = re.compile(r"[-]+")


def slugify(text: str, maxlen: int = 200) -> str:
    if not text:
        return ""
    # Normalize unicode, remove accents
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    # Remove invalid chars, keep alnum and spaces and hyphens
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    # Replace spaces with dashes
    text = re.sub(r"\s+", "-", text).strip("-")
    text = _dashes_re.sub("-", text)
    return text[:maxlen].strip("-")


def generate_unique_slug(session, model, value, column="public_slug", maxlen=200):
    """
    Genera un slug único consultando una vez la BD por slugs con el mismo prefijo
    y calculando localmente el sufijo numérico siguiente disponible.
    """
    base = slugify(value, maxlen=maxlen)
    col = getattr(model, column)

    # Traer todos los slugs que comienzan por la base (base o base-...)
    like_pattern = f"{base}%"
    rows = session.query(col).filter(col.like(like_pattern)).all()
    existing = {r[0] for r in rows if r and isinstance(r[0], str)}

    # Si la base no existe, devolverla directamente
    if base not in existing:
        return base

    # Extraer sufijos numéricos usados para base-N
    used = set()
    for s in existing:
        if s == base:
            used.add(0)
        elif s.startswith(base + "-"):
            suf = s[len(base) + 1 :]
            if suf.isdigit():
                used.add(int(suf))

    # Buscar el menor entero positivo no usado
    i = 1
    while i in used:
        i += 1

    # Construir candidato teniendo en cuenta maxlen; si hay colisión por truncado,
    # seguir incrementando i (todo en memoria: sin nuevas consultas)
    while True:
        suffix = f"-{i}"
        if len(base) + len(suffix) > maxlen:
            trunc_base = base[: maxlen - len(suffix)]
        else:
            trunc_base = base
        candidate = f"{trunc_base}{suffix}"
        if candidate not in existing:
            return candidate
        i += 1
        if i > 10000:
            raise RuntimeError("Unable to generate unique slug")
