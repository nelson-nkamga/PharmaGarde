"""Utilitaires texte : normalisation (accents/casse) et pluriel des formes galéniques."""
import unicodedata


def norm(value) -> str:
    """Minuscule sans accents, espaces compactés. Sert aux recherches insensibles aux accents."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())


_INVARIABLES = {"à", "a", "de", "du", "des", "la", "le", "croquer", "boire", "sur", "pour", "en"}


def pluriel(forme: str) -> str:
    """« Comprimé dispersible » -> « Comprimés dispersibles »."""
    mots = []
    for mot in (forme or "").split():
        bas = mot.lower()
        if bas in _INVARIABLES or bas.endswith(("s", "x", "z")) or not mot[0].isalpha():
            mots.append(mot)
        else:
            mots.append(mot + "s")
    return " ".join(mots)


def like_pattern(terme: str) -> str:
    """Motif LIKE sûr : échappe % et _ (la clause SQL utilise ESCAPE '\\')."""
    t = norm(terme).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{t}%"
