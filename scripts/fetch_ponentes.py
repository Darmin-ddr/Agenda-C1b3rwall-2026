"""
Descarga ponentes y ponencias de C1b3rwall, los cruza y genera ponentes.json.
Uso: python scripts/fetch_ponentes.py
"""

import json
import re
import unicodedata
import urllib.request
from pathlib import Path

YEAR = "2026"
BASE = "https://c1b3rwall.policia.es"
PONENTES_URL  = f"{BASE}/content/congreso/{YEAR}/ponentes_json.json"
PONENCIAS_URL = f"{BASE}/content/congreso/{YEAR}/ponencias_json.json"
BASE_IMG      = BASE
HTML_FILE     = Path("index.html")


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def norm(s):
    """Nombre normalizado para cruce sin tildes ni mayúsculas ni espacios."""
    s = unicodedata.normalize("NFD", s.lower().strip())
    s = re.sub(r"[̀-ͯ]", "", s)
    return re.sub(r"\s+", "", s)


def main():
    print("Descargando ponentes...")
    ponentes_raw = fetch_json(PONENTES_URL)
    print(f"  {len(ponentes_raw)} ponentes")

    print("Descargando ponencias...")
    ponencias = fetch_json(PONENCIAS_URL)
    print(f"  {len(ponencias)} sesiones")

    # Lookup ponente por nombre normalizado
    by_name = {norm(p["Nombre"]): p for p in ponentes_raw}

    # Charlas por nombre normalizado del ponente
    talks_by_name: dict[str, list] = {}
    for sesion in ponencias:
        for sp in sesion.get("Ponentes", []):
            key = norm(sp.get("Nombre", ""))
            talk = {
                "titulo":     sesion.get("Título", ""),
                "dia":        sesion.get("Día", ""),
                "hora":       sesion.get("Hora", ""),
                "aula":       sesion.get("Ubicación", ""),
                "actividad":  sesion.get("Actividad", ""),
                "restriccion": sesion.get("Restricción", ""),
            }
            talks_by_name.setdefault(key, []).append(talk)

    result = []
    seen: set[str] = set()

    # Ponentes del JSON principal (con bio y org)
    for p in ponentes_raw:
        key = norm(p["Nombre"])
        seen.add(key)
        foto = p.get("Foto", "")
        result.append({
            "id":      p["ID"],
            "nombre":  p["Nombre"],
            "foto":    BASE_IMG + foto if foto else "",
            "bio":     p.get("Biografía", ""),
            "org":     p.get("Organización", ""),
            "charlas": talks_by_name.get(key, []),
        })

    # Ponentes que aparecen en ponencias pero no en el JSON de ponentes
    extra_seen: set[str] = set()
    for sesion in ponencias:
        for sp in sesion.get("Ponentes", []):
            key = norm(sp.get("Nombre", ""))
            if key in seen or key in extra_seen:
                continue
            extra_seen.add(key)
            foto = sp.get("Foto", "")
            result.append({
                "id":      sp.get("ID", ""),
                "nombre":  sp.get("Nombre", ""),
                "foto":    BASE_IMG + foto if foto else "",
                "bio":     "",
                "org":     "",
                "charlas": talks_by_name.get(key, []),
            })

    result.sort(key=lambda x: norm(x["nombre"]))
    matched = sum(1 for p in result if p["charlas"])
    print(f"{len(result)} ponentes ({matched} con charlas vinculadas)")

    ponentes_json = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
    tag = f'<script id="embeddedPonentes" type="application/json">{ponentes_json}</script>'

    html = HTML_FILE.read_text(encoding="utf-8")
    new_html, n = re.subn(
        r'<script\s+id="embeddedPonentes"[^>]*>.*?</script>',
        lambda _: tag, html, flags=re.DOTALL,
    )
    if n == 0:
        new_html = re.sub(
            r'(<script\s+id="embeddedIcs"[^>]*>.*?</script>)',
            lambda m: m.group(1) + "\n  " + tag, html, flags=re.DOTALL,
        )
    HTML_FILE.write_text(new_html, encoding="utf-8")
    print(f"index.html actualizado con ponentes embebidos")


if __name__ == "__main__":
    main()
