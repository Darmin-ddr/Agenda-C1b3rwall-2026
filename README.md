# Agenda C1b3rwall 2026

### 🌐 https://darmin-ddr.github.io/Agenda-C1b3rwall-2026/

App web PWA para consultar el programa del Congreso C1b3rwall 2026 (2, 3 y 4 de junio · Escuela Nacional de Policía).

## Funcionalidades

- Búsqueda por charla, ponente, aula o tema
- Filtros por día, aula, categoría y dificultad
- Vista de lista, parrilla horaria y "Ahora"
- Agenda personal con exportación a calendario (.ics)
- Modo claro / oscuro
- Funciona offline (PWA)
- Programa actualizado automáticamente desde la web oficial cada 15 minutos

## Actualización automática

Un workflow de GitHub Actions comprueba cada 15 minutos si la organización ha publicado cambios en el programa. Si los hay, descarga el JSON oficial, regenera el ICS embebido y republica la web automáticamente.

Ver [NOTES.md](NOTES.md) para documentación técnica detallada.
