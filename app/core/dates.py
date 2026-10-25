"""Dates : stockage en UTC, affichage à l'heure de Douala (UTC+1, sans changement d'heure)."""
from datetime import datetime, timedelta, timezone

from flask import current_app

UTC = timezone.utc
DOUALA = timezone(timedelta(hours=1), "WAT")

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
_FMT = "%Y-%m-%dT%H:%M:%SZ"


def now_utc() -> datetime:
    """Instant courant (ou instant de démonstration figé via PHARMA_DEMO_NOW, heure de Douala)."""
    demo = current_app.config.get("DEMO_NOW")
    if demo:
        return datetime.fromisoformat(demo).replace(tzinfo=DOUALA).astimezone(UTC)
    return datetime.now(UTC)


def to_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime(_FMT)


def parse(value: str) -> datetime:
    return datetime.strptime(value, _FMT).replace(tzinfo=UTC)


def local(dt: datetime) -> datetime:
    return dt.astimezone(DOUALA)


def from_local(date_str: str, time_str: str) -> datetime:
    """'2026-10-12' + '20:00' (heure de Douala) -> datetime UTC. Lève ValueError."""
    naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=DOUALA).astimezone(UTC)


def monday_of(dt: datetime) -> datetime:
    """Lundi 00h00 (heure de Douala) de la semaine de dt, en UTC."""
    l = local(dt)
    start = (l - timedelta(days=l.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


# ---- Formats d'affichage (français) ------------------------------------------------
def date_fr(dt: datetime, annee: bool = True) -> str:
    l = local(dt)
    s = f"{l.day} {MOIS[l.month - 1]}"
    return f"{s} {l.year}" if annee else s


def jour_fr(dt: datetime) -> str:
    return JOURS[local(dt).weekday()].capitalize()


def heure_fr(dt: datetime) -> str:
    l = local(dt)
    return f"{l.hour:02d}h{l.minute:02d}"


def heure_courte(dt: datetime) -> str:
    l = local(dt)
    return f"{l.hour:02d}h" if l.minute == 0 else f"{l.hour:02d}h{l.minute:02d}"


def jj_mm(dt: datetime) -> str:
    l = local(dt)
    return f"{l.day:02d}/{l.month:02d}"


def mois_annee(dt: datetime) -> str:
    l = local(dt)
    return f"{MOIS[l.month - 1].capitalize()} {l.year}"


def plage_semaine(debut: datetime) -> str:
    """12–18 octobre 2026 (ou 28 septembre–4 octobre 2026)."""
    a, b = local(debut), local(debut + timedelta(days=6))
    if a.month == b.month:
        return f"{a.day}–{b.day} {MOIS[b.month - 1]} {b.year}"
    return f"{a.day} {MOIS[a.month - 1]}–{b.day} {MOIS[b.month - 1]} {b.year}"


def jour_local(dt: datetime):
    return local(dt).date()


def lendemain(debut: datetime, fin: datetime) -> bool:
    return local(fin).date() > local(debut).date()


# ---- Ancienneté d'un stock (règle R3) -------------------------------------------------
def anciennete(mis_a_jour: datetime, now: datetime | None = None) -> dict:
    now = now or now_utc()
    cfg = current_app.config
    delta = now - mis_a_jour
    jours = max(delta.days, 0)
    if jours < cfg["SEUIL_RECENT_JOURS"]:
        niveau = "recent"
    elif jours <= cfg["SEUIL_ANCIEN_JOURS"]:
        niveau = "moyen"
    else:
        niveau = "ancien"
    if jours == 0:
        texte, court = "Mis à jour aujourd'hui", "Aujourd'hui · moins de 1 jour"
    elif jours == 1:
        texte, court = "Mis à jour il y a 1 jour", "Il y a 1 jour"
    else:
        texte, court = f"Mis à jour il y a {jours} jours", f"Il y a {jours} jours"
    return {"jours": jours, "niveau": niveau, "texte": texte, "court": court,
            "a_confirmer": niveau != "recent"}
