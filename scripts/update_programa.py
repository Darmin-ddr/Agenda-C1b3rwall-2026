"""
Comprueba si el programa o los ponentes de C1b3rwall han sido actualizados,
descarga los JSON, convierte ponencias a ICS (embebido en index.html)
y regenera ponentes.json si hay cambios.
"""

import re
import json
import sys
import base64
import hashlib
import unicodedata
import urllib.request
from pathlib import Path

YEAR = "2026"
BASE = "https://c1b3rwall.policia.es"
CONGRESO_URL      = f"{BASE}/congreso"
PONENCIAS_URL     = f"{BASE}/content/congreso/{YEAR}/ponencias_json.json"
PONENTES_URL      = f"{BASE}/content/congreso/{YEAR}/ponentes_json.json"
LAST_UPDATE_FILE  = Path(".last-program-update")
LAST_PONENTES_HASH = Path(".last-ponentes-hash")
HTML_FILE         = Path("index.html")
PONENTES_FILE     = Path("ponentes.json")

# Spain en junio = CEST (UTC+2)
TZ_OFFSET = 2

DIAS = {
    "martes":    (2026, 6, 2),
    "miercoles": (2026, 6, 3),
    "miércoles": (2026, 6, 3),
    "jueves":    (2026, 6, 4),
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def extract_timestamp(html):
    # Busca el timestamp del bloque "Programa" específicamente
    m = re.search(
        r'Programa[\s\S]{0,400}?Actualizado a\s*([\d/]+\s*\|\s*[\d:]+)\s*horas',
        html, re.IGNORECASE
    )
    if not m:
        m = re.search(r'Actualizado a\s*([\d/]+\s*\|\s*[\d:]+)\s*horas', html)
    return m.group(1).strip() if m else None


def parse_day(dia_str):
    normalized = (dia_str.lower().strip()
                  .replace("á", "a").replace("é", "e").replace("í", "i")
                  .replace("ó", "o").replace("ú", "u"))
    for key, val in DIAS.items():
        key_norm = key.replace("é", "e").replace("á", "a")
        if key_norm in normalized or key in dia_str.lower():
            return val
    return None


def parse_time(hora_str):
    hora_str = hora_str.replace("–", "-").replace("—", "-")
    m = re.match(r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})', hora_str.strip())
    return tuple(int(x) for x in m.groups()) if m else None


def to_utc_ics(year, month, day, hour, minute):
    utc_h = hour - TZ_OFFSET
    utc_d = day
    if utc_h < 0:
        utc_h += 24
        utc_d -= 1
    return f"{year:04d}{month:02d}{utc_d:02d}T{utc_h:02d}{minute:02d}00Z"


def esc(value):
    return (str(value or "")
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace(",", "\\,")
            .replace(";", "\\;"))


def json_to_ics(sessions):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Agenda C1b3rwall//ES"]

    for i, s in enumerate(sessions):
        day = parse_day(s.get("Día", ""))
        time = parse_time(s.get("Hora", ""))
        titulo = (s.get("Título") or "").strip()

        if not day or not time or not titulo:
            continue

        year, month, day_num = day
        sh, sm, eh, em = time
        dtstart = to_utc_ics(year, month, day_num, sh, sm)
        dtend   = to_utc_ics(year, month, day_num, eh, em)

        ponentes = ", ".join(
            p["Nombre"] for p in s.get("Ponentes", []) if p.get("Nombre")
        )

        desc_parts = []
        if ponentes:
            desc_parts.append(f"Ponentes: {ponentes}")
        if s.get("Descripción"):
            desc_parts.append(s["Descripción"])
        extras = [
            f"Dificultad: {s['Dificultad']}" if s.get("Dificultad") else "",
            f"Idioma: {s['Idioma']}"         if s.get("Idioma")      else "",
            f"Actividad: {s['Actividad']}"   if s.get("Actividad")   else "",
            f"Restricción: {s['Restricción']}" if s.get("Restricción") else "",
        ]
        extras = [x for x in extras if x]
        if extras:
            desc_parts.append(" | ".join(extras))
        if s.get("Consejos"):
            desc_parts.append(f"Consejos: {s['Consejos']}")

        desc_text = "\n\n".join(desc_parts)
        uid_hash = hashlib.sha1(f"{titulo}|{dtstart}".encode()).hexdigest()[:10]
        lines += [
            "BEGIN:VEVENT",
            f"UID:cw26-{uid_hash}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{esc(titulo)}",
            f"DESCRIPTION:{esc(desc_text)}",
            f"LOCATION:{esc(s.get('Ubicación', ''))}",
            f"CATEGORIES:{esc(s.get('Actividad', ''))}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def embed_ics(html, ics, timestamp):
    b64 = base64.b64encode(ics.encode("utf-8")).decode("ascii")

    def replace_tag(m):
        after_id = re.sub(r'\s*data-updated="[^"]*"', "", m.group(1))
        return f'<script id="embeddedIcs"{after_id} data-updated="{timestamp}">{b64}</script>'

    new_html, n = re.subn(
        r'<script\s+id="embeddedIcs"([^>]*)>.*?</script>',
        replace_tag,
        html,
        flags=re.DOTALL,
    )
    return new_html, n > 0


def norm_name(s):
    s = unicodedata.normalize("NFD", s.lower().strip())
    s = re.sub(r"[̀-ͯ]", "", s)
    return re.sub(r"\s+", "", s)


def build_ponentes_json(ponentes_raw, sessions):
    by_name = {norm_name(p["Nombre"]): p for p in ponentes_raw}

    talks_by_name: dict = {}
    for sesion in sessions:
        for sp in sesion.get("Ponentes", []):
            key = norm_name(sp.get("Nombre", ""))
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
    seen: set = set()

    for p in ponentes_raw:
        key = norm_name(p["Nombre"])
        seen.add(key)
        foto = p.get("Foto", "")
        result.append({
            "id":      p["ID"],
            "nombre":  p["Nombre"],
            "foto":    BASE + foto if foto else "",
            "bio":     p.get("Biografía", ""),
            "org":     p.get("Organización", ""),
            "charlas": talks_by_name.get(key, []),
        })

    extra_seen: set = set()
    for sesion in sessions:
        for sp in sesion.get("Ponentes", []):
            key = norm_name(sp.get("Nombre", ""))
            if key in seen or key in extra_seen:
                continue
            extra_seen.add(key)
            foto = sp.get("Foto", "")
            result.append({
                "id":      sp.get("ID", ""),
                "nombre":  sp.get("Nombre", ""),
                "foto":    BASE + foto if foto else "",
                "bio":     "",
                "org":     "",
                "charlas": talks_by_name.get(key, []),
            })

    result.sort(key=lambda x: norm_name(x["nombre"]))
    return result


def update_ponentes(sessions):
    print("Comprobando ponentes...")
    try:
        raw = fetch(PONENTES_URL)
    except Exception as e:
        print(f"Error al obtener ponentes: {e}")
        return False

    new_hash = hashlib.sha1(raw.encode()).hexdigest()
    old_hash = LAST_PONENTES_HASH.read_text(encoding="utf-8").strip() if LAST_PONENTES_HASH.exists() else ""

    if new_hash == old_hash:
        print("Ponentes sin cambios")
        return False

    print(f"Cambio en ponentes detectado (hash {old_hash[:8] or 'ninguno'} → {new_hash[:8]})")
    ponentes_raw = json.loads(raw)
    merged = build_ponentes_json(ponentes_raw, sessions)
    matched = sum(1 for p in merged if p["charlas"])

    merged_json = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    LAST_PONENTES_HASH.write_text(new_hash, encoding="utf-8")
    print(f"Ponentes listos: {len(merged)} ponentes, {matched} con charlas vinculadas")
    return merged_json


def embed_ponentes(html, ponentes_json):
    tag = f'<script id="embeddedPonentes" type="application/json">{ponentes_json}</script>'
    new_html, n = re.subn(
        r'<script\s+id="embeddedPonentes"[^>]*>.*?</script>',
        lambda _: tag,
        html,
        flags=re.DOTALL,
    )
    if n == 0:
        new_html = re.sub(
            r'(<script\s+id="embeddedIcs"[^>]*>.*?</script>)',
            lambda m: m.group(1) + "\n  " + tag,
            html,
            flags=re.DOTALL,
        )
    return new_html


def main():
    print("Comprobando timestamp del programa...")
    try:
        congreso_html = fetch(CONGRESO_URL)
    except Exception as e:
        print(f"Error al obtener página del congreso: {e}")
        sys.exit(0)

    timestamp = extract_timestamp(congreso_html)
    if not timestamp:
        print("No se encontró timestamp — abortando sin cambios")
        sys.exit(0)

    print(f"Timestamp actual: {timestamp}")
    last = LAST_UPDATE_FILE.read_text(encoding="utf-8").strip() if LAST_UPDATE_FILE.exists() else ""

    programa_changed = timestamp != last

    try:
        raw_sessions = fetch(PONENCIAS_URL)
        sessions = json.loads(raw_sessions)
    except Exception as e:
        print(f"Error al obtener ponencias: {e}")
        sys.exit(1)

    ponentes_json = update_ponentes(sessions)
    ponentes_changed = bool(ponentes_json)

    if not programa_changed and not ponentes_changed:
        print("Sin cambios en programa ni ponentes, nada que hacer")
        sys.exit(0)

    html = HTML_FILE.read_text(encoding="utf-8")

    if programa_changed:
        print(f"Cambio de programa detectado: '{last}' -> '{timestamp}'")
        print(f"Ponencias cargadas: {len(sessions)}")
        ics = json_to_ics(sessions)
        valid = ics.count("BEGIN:VEVENT")
        print(f"Eventos ICS generados: {valid}")
        html, ok = embed_ics(html, ics, timestamp)
        if not ok:
            print("Error: no se encontró el tag #embeddedIcs en index.html")
            sys.exit(1)
        LAST_UPDATE_FILE.write_text(timestamp, encoding="utf-8")

    if ponentes_changed:
        html = embed_ponentes(html, ponentes_json)

    HTML_FILE.write_text(html, encoding="utf-8")
    print("index.html actualizado")


if __name__ == "__main__":
    main()
