# Agenda C1b3rwall — Notas del proyecto

App web PWA de una sola página (`index.html`) para consultar el programa del Congreso C1b3rwall. Publicada en GitHub Pages.

---

## Arquitectura general

Todo el contenido dinámico viaja **embebido dentro del propio `index.html`** — no hay llamadas externas en runtime. Funciona offline desde la primera carga (PWA con Service Worker).

Hay dos bloques embebidos:

```html
<!-- Programa: ICS en base64 -->
<script id="embeddedIcs" type="application/octet-stream"
        data-encoding="base64" data-updated="01/06/2026 | 18:52">
  BASE64...
</script>

<!-- Ponentes: JSON compacto -->
<script id="embeddedPonentes" type="application/json">
  [{"id":"...","nombre":"...","foto":"...","bio":"...","org":"...","charlas":[...]},...]
</script>
```

La app lee ambos bloques al arrancar (`loadEventsFromIcs` y `loadPonentes`), los parsea y construye la interfaz.

**Por qué embebido y no fetch:** permite abrir `index.html` directamente sin servidor, funciona offline sin Service Worker activo, y simplifica el despliegue (un solo fichero).

**Gotcha al embeber JSON con regex:** usar siempre lambda como reemplazo en `re.subn` para evitar que los `\n` del JSON se conviertan en saltos de línea literales:
```python
re.subn(pattern, lambda _: tag, html, flags=re.DOTALL)
```

---

## Fuentes de datos

| Recurso | URL |
|---|---|
| Página del congreso (timestamp) | `https://c1b3rwall.policia.es/congreso` |
| JSON de ponencias | `https://c1b3rwall.policia.es/content/congreso/2026/ponencias_json.json` |
| JSON de ponentes | `https://c1b3rwall.policia.es/content/congreso/2026/ponentes_json.json` |

Estas URLs se descubrieron inspeccionando las peticiones de red del sitio oficial desde la consola del navegador (`fetch('/content/congreso/2026/ponencias_json.json').then(r=>r.json()).then(console.log)`). El patrón de URL llevó a deducir el endpoint de ponentes.

### Estructura del JSON de ponencias (~294 sesiones)
Campos por sesión: `Día`, `Hora`, `Ubicación`, `Actividad`, `Idioma`, `Dificultad`, `Título`, `Restricción`, `Descripción`, `Consejos`, `Ponentes[]` (array con `{Nombre, ID, Foto}`).

### Estructura del JSON de ponentes (~280 entradas)
Campos: `Nombre`, `ID`, `Foto` (ruta relativa `/img/ponentes_2026/{ID}.jpg`), `Biografía`, `Organización`. Los campos `Cargo`, `Email`, `Linkedin` y `Web` estaban vacíos en 2026.

### Cruce ponente ↔ charla
El JSON de ponencias incluye `Ponentes[].Nombre` por sesión. El cruce con el JSON de ponentes se hace por **nombre normalizado** (minúsculas, sin tildes, sin espacios) porque los IDs no son consistentes entre los dos endpoints. Resultado en 2026: 319 de 337 ponentes con charlas vinculadas.

---

## Auto-update (pipeline GitHub Actions)

### Flujo

1. `scripts/update_programa.py` hace fetch de `/congreso` y extrae `"Actualizado a DD/MM/YYYY | HH:MM horas"`.
2. Compara con `.last-program-update`. Si cambió el programa → regenera el ICS y lo embebe en `index.html`.
3. Hace fetch de `ponentes_json.json`, calcula su SHA1 y compara con `.last-ponentes-hash`. Si cambió → regenera `ponentes.json` mergeado y lo embebe en `index.html`.
4. Si hubo cualquier cambio → el workflow hace commit + push a `main` → GitHub Pages republica.

El cron está **desactivado** tras el congreso de 2026 (solo `workflow_dispatch` manual). Para 2027: reactivar el `schedule` en el workflow.

### Detección de cambios
- **Programa**: timestamp textual extraído del HTML de `/congreso`.
- **Ponentes**: hash SHA1 del JSON crudo — no tiene timestamp propio.

### Configuración necesaria en GitHub
En **Settings → Actions → General → Workflow permissions**: marcar **"Read and write permissions"**.

---

## Scripts de utilidad

### `scripts/update_programa.py`
Script principal que ejecuta el pipeline completo (programa + ponentes). Usado por el workflow de GitHub Actions.

### `scripts/fetch_ponentes.py`
Script standalone para regenerar y embeber los ponentes manualmente:
```
python scripts/fetch_ponentes.py
```
Útil para actualizar ponentes sin tocar el programa, o para preparar la siguiente edición.

---

## Estructura de la app (rama `feature/ponentes`)

### Vistas / pestañas
| Pestaña | Descripción |
|---|---|
| Programa | Lista de charlas agrupadas por franja horaria, filtrable |
| Mi agenda | Charlas guardadas por el usuario |
| Parrilla | Vista de calendario por aula y hora |
| Ahora | Charlas en curso y próximas |
| **Ponentes** | Grid de ponentes con búsqueda por nombre/organización |

### Ponentes — integración UI

**Grid de ponentes** (`renderPonentes`):
- Grid responsive con tarjetas de foto cuadrada + nombre + organización en turquesa.
- Búsqueda integrada en el buscador principal del topbar (filtra por nombre y organización cuando la vista activa es "ponentes").
- Los filtros de día/aula se ocultan automáticamente en esta vista.

**Chips de ponente en tarjetas de charla** (`speakerChipsHtml`):
- Cada charla muestra chips `[foto circular · nombre]` por ponente.
- Aparecen en: tarjetas del programa, tarjetas de agenda, modal de detalles.
- Al clicar un chip se abre la ficha del ponente (independientemente de dónde esté el chip).
- Fallback a iniciales con gradiente brand→accent si la foto no carga (`speakerThumbErr`).

**Ficha de ponente** (`showSpeaker`):
- Modal con foto, nombre, organización, bio y lista de sus charlas (día, hora, aula).

### Estado de ponentes en `state`
```javascript
state.ponentes  // Map: normP(nombre) → ponente object
```
`normP(s)` = minúsculas + sin tildes (NFD) + sin espacios. Es la clave de cruce con los nombres que vienen del ICS.

---

## Despliegue — regla del Service Worker

Cada vez que se hace push de cambios significativos a `main` hay que **incrementar el número de versión** en `sw.js`:

```js
const CACHE_NAME = "ciberwall-agenda-v26"; // ← subir este número
```

Si no se hace, los usuarios que tienen la PWA instalada siguen viendo la versión antigua cacheada aunque GitHub Pages ya sirva la nueva. Un hard refresh (`Ctrl+Shift+R`) o incógnito lo fuerza en el navegador, pero los usuarios normales no lo harán.

**Cuándo es obligatorio:** al cambiar `index.html`, `sw.js` o cualquier asset listado en `ASSETS`. No hace falta para cambios solo en scripts de Python o el workflow.

---

## Cierre de edición

Al terminar el congreso, `main` pasa a servir una **página de agradecimiento** estática (`index.html` simplificado) que mantiene el estilo Ciberwall (logo, colores, tema claro/oscuro) con el mensaje "¡Gracias por estar en C1b3rwall 2026!" y "¡Nos vemos en C1b3rwall 2027!" en turquesa.

El workflow queda con solo `workflow_dispatch` (sin cron) hasta la próxima edición.

---

## Cambios de UI históricos (2026)

- **Barra de navegación móvil**: `position: fixed` en la parte inferior, fondo opaco con borde y sombra hacia arriba para que destaque sobre el contenido.
- **Stats**: condensado a una sola línea `"X sesiones · X aulas · X en agenda"` (antes tres pills separados).
- **Botón de tema**: botón simple ☾/☀ en el topbar (antes menú hamburguesa desplegable).
- **Timestamp de actualización**: línea pequeña bajo las stats con la hora de publicación oficial (no la del cron).

---

## Estructura de ficheros

```
index.html                             — App completa o página de cierre (según rama/momento)
sw.js                                  — Service Worker (PWA / offline)
manifest.webmanifest                   — Metadatos PWA
ponentes_test.html                     — Prototipo standalone de la vista de ponentes
scripts/
  update_programa.py                   — Pipeline completo (programa + ponentes)
  fetch_ponentes.py                    — Regenerar/embeber ponentes manualmente
.github/workflows/
  update-programa.yml                  — GitHub Actions (cron desactivado tras congreso)
.last-program-update                   — Timestamp del último programa procesado
.last-ponentes-hash                    — SHA1 del último JSON de ponentes procesado
```

### Ramas
- `main` — página de agradecimiento (publicada en GitHub Pages)
- `feature/ponentes` — app completa con pestaña de ponentes (base para 2027)

---

## Lista de tareas para 2027

### App y datos
- [ ] Cambiar `YEAR = "2026"` a `"2027"` en `update_programa.py` y `fetch_ponentes.py`
- [ ] Reactivar el `schedule` (cron) en `.github/workflows/update-programa.yml`
- [ ] Restaurar `main` desde `feature/ponentes` (o mergear); eliminar overlay de agradecimiento 2026
- [ ] Actualizar textos hardcodeados: fechas del congreso, título, descripción, mensaje del restore banner
- [ ] Bump de la versión del Service Worker (`sw.js`) para forzar actualización de caché

### PWA — instalación y notificaciones push
La app es **no oficial**, así que la distribución es solo vía web (sin App Store ni Play Store).
El objetivo es maximizar la tasa de instalación como PWA y añadir notificaciones push.

- [ ] **Banner de instalación personalizado**
  - Android/Chrome: interceptar el evento `beforeinstallprompt`, guardarlo y mostrar un banner
    propio con contexto ("Instala la app para recibir avisos de tus charlas") en lugar del prompt genérico del navegador.
  - iOS/Safari: no hay evento automático. Detectar `navigator.standalone === false` en Safari iOS
    y mostrar un tooltip/modal con instrucciones: "Pulsa Share (⬆) → Añadir a pantalla de inicio".
  - Guardar en localStorage si el usuario ya instaló o descartó el banner para no volver a mostrarlo.

- [ ] **Push notifications**
  - El Service Worker ya existe — solo hay que añadir el handler de `push`.
  - Usar **OneSignal** (plan gratuito): gestiona suscripciones, VAPID keys y el panel de envío
    sin necesidad de backend propio. SDK de unas pocas líneas en el SW y en el HTML.
  - Casos de uso: "Tu charla empieza en 15 minutos", "Cambio de aula en una charla guardada".
  - El envío de notificaciones se haría manualmente desde el panel de OneSignal durante el congreso.

- [ ] **Icono PWA**
  - Revisar `icon.svg` y `logo_26.png` para que queden bien en pantalla de inicio en iOS y Android
    (fondo opaco, padding suficiente, tamaños 192×192 y 512×512 en `manifest.webmanifest`).
