# Agenda C1b3rwall 2026 — Notas del proyecto

App web PWA de una sola página (`index.html`) para consultar el programa del Congreso C1b3rwall 2026. Publicada en GitHub Pages.

---

## Arquitectura

Todo el programa viaja embebido dentro del propio `index.html` como un bloque ICS en base64:

```html
<script id="embeddedIcs" type="application/octet-stream"
        data-encoding="base64" data-updated="01/06/2026 | 18:52">
  BASE64_DEL_ICS...
</script>
```

La app lee ese bloque al arrancar, lo parsea y construye la interfaz. No hace llamadas externas en runtime — funciona offline una vez cargada (PWA con Service Worker).

---

## Auto-update del programa

El programa oficial se actualiza en `c1b3rwall.policia.es`. Para mantener la app sincronizada automáticamente hay un pipeline en GitHub Actions.

### Fuentes de datos

| Recurso | URL |
|---|---|
| Página del congreso (timestamp) | `https://c1b3rwall.policia.es/congreso` |
| JSON de ponencias | `https://c1b3rwall.policia.es/content/congreso/2026/ponencias_json.json` |

El JSON contiene ~294 sesiones con los campos: `Día`, `Hora`, `Ubicación`, `Actividad`, `Idioma`, `Dificultad`, `Título`, `Restricción`, `Descripción`, `Consejos`, `Ponentes[]`.

### Flujo cada 15 minutos

1. **`scripts/update_programa.py`** hace fetch de `/congreso` y extrae el texto `"Actualizado a DD/MM/YYYY | HH:MM horas"` del bloque Programa.
2. Compara ese timestamp con el guardado en `.last-program-update`.
3. Si **no cambió** → termina sin tocar nada.
4. Si **cambió** → descarga el JSON, convierte a ICS (horarios a UTC, CEST = UTC+2), embebe el ICS en base64 en `index.html` y escribe el timestamp como atributo `data-updated`.
5. **`.github/workflows/update-programa.yml`** hace commit + push a `main`.
6. GitHub Pages republica la web automáticamente.

### Configuración necesaria en GitHub

En **Settings → Actions → General → Workflow permissions**: marcar **"Read and write permissions"** para que el workflow pueda hacer push.

El workflow también tiene `workflow_dispatch`, así que se puede lanzar manualmente desde la pestaña Actions sin esperar al cron.

---

## Cambios de UI realizados

### Barra de navegación móvil
- En móvil la barra `Programa / Mi agenda / Parrilla / Ahora` es `position: fixed` en la parte inferior.
- **Problema original**: fondo casi idéntico al de la página → se perdía visualmente.
- **Fix**: fondo blanco opaco en claro (`rgba(255,255,255,.97)`), azul oscuro más claro en oscuro (`rgba(26,40,57,.97)`), borde superior con tinte brand, sombra redirigida hacia arriba (`0 -6px 24px`).

### Stats
- **Antes**: tres pills separados `"X sesiones visibles"` / `"X aulas"` / `"X en mi agenda aquí"` en flex-wrap → wrapping en pantallas pequeñas.
- **Ahora**: una sola línea `"X sesiones · X aulas · X en agenda"`.

### Botón de tema
- **Antes**: menú hamburguesa con panel desplegable (tema + importar ICS).
- **Ahora**: botón simple ☾/☀ que alterna claro/oscuro. El tema se persiste en `localStorage`.

### Timestamp de actualización
- Línea pequeña centrada bajo las stats: `"Datos actualizados: DD/MM/YYYY | HH:MM"`.
- El valor es el timestamp de publicación de la organización, no la hora del cron.
- La app lo lee del atributo `data-updated` del tag `#embeddedIcs`.

---

## Estructura de ficheros relevantes

```
index.html                          — App completa (CSS + HTML + JS + ICS embebido)
sw.js                               — Service Worker para PWA / offline
manifest.webmanifest                — Metadatos PWA
scripts/update_programa.py          — Script de actualización automática
.github/workflows/update-programa.yml — Workflow de GitHub Actions (cron 15 min)
.last-program-update                — Timestamp del último programa procesado
```
