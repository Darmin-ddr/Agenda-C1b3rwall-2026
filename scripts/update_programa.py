"""
Comprueba si el programa de C1b3rwall 2026 ha sido actualizado,
descarga el JSON de ponencias, lo convierte a ICS y lo embebe en index.html.
"""

import re
import json
import sys
import base64
import urllib.request
from pathlib import Path

CONGRESO_URL = "https://c1b3rwall.policia.es/congreso"
PONENCIAS_URL = "https://c1b3rwall.policia.es/content/congreso/2026/ponencias_json.json"
LAST_UPDATE_FILE = Path(".last-program-update")
HTML_FILE = Path("index.html")

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

        lines += [
            "BEGIN:VEVENT",
            f"UID:ciberwall2026-{i+1:03d}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{esc(titulo)}",
            f"DESCRIPTION:{esc(chr(10).join(desc_parts))}",
            f"LOCATION:{esc(s.get('Ubicación', ''))}",
            f"CATEGORIES:{esc(s.get('Actividad', ''))}",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def embed_ics(html, ics, timestamp):
    b64 = base64.b64encode(ics.encode("utf-8")).decode("ascii")
    # Update base64 content and data-updated attribute
    new_html, n = re.subn(
        r'<script([^>]+)id="embeddedIcs"([^>]*)>.*?(</script>)',
        lambda m: f'<script{m.group(1)}id="embeddedIcs"{m.group(2)} data-updated="{timestamp}">{b64}{m.group(3)}',
        html,
        flags=re.DOTALL,
    )
    return new_html, n > 0


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

    if timestamp == last:
        print("Sin cambios, nada que hacer")
        sys.exit(0)

    print(f"Cambio detectado: '{last}' -> '{timestamp}'")

    try:
        raw = fetch(PONENCIAS_URL)
        sessions = json.loads(raw)
    except Exception as e:
        print(f"Error al obtener ponencias: {e}")
        sys.exit(1)

    print(f"Ponencias cargadas: {len(sessions)}")

    ics = json_to_ics(sessions)
    valid = ics.count("BEGIN:VEVENT")
    print(f"Eventos ICS generados: {valid}")

    html = HTML_FILE.read_text(encoding="utf-8")
    new_html, ok = embed_ics(html, ics, timestamp)

    if not ok:
        print("Error: no se encontró el tag #embeddedIcs en index.html")
        sys.exit(1)

    HTML_FILE.write_text(new_html, encoding="utf-8")
    LAST_UPDATE_FILE.write_text(timestamp, encoding="utf-8")
    print(f"index.html actualizado con {valid} eventos")


if __name__ == "__main__":
    main()
