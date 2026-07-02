# 🏆 Calendario Dinámico - Mundial 2026

Un sistema de calendario dinámico (formato `.ics`) para el Mundial de la FIFA 2026 que se actualiza automáticamente en tiempo real con marcadores, goles y estatus en vivo.

## 🌟 Características
- **100% Gratuito:** Utiliza GitHub Pages y GitHub Actions.
- **En Vivo:** Actualiza los marcadores cada 5 minutos usando los datos de `football-data.org`.
- **Cuotas de Apuestas:** Muestra las cuotas (momios) promedio de cada partido, actualizadas cada 2 horas con `The Odds API`.
- **Inteligente:** Algoritmo que solo consume peticiones a la API cuando detecta que hay un partido jugándose, optimizando el uso para el plan gratuito.
- **Multiplataforma:** Compatible con iOS (iPhone/iPad), Mac, Google Calendar (Android) y Outlook.

## 🔗 Suscripción (URLs Públicas)
Tus amigos o usuarios pueden añadir el calendario usando estos enlaces:

- **Para dispositivos Apple (iOS / macOS):**
  `webcal://kristianedu.github.io/calendario-mundial/mundial_2026_dinamico.ics`

- **Para Google Calendar (Android / Web):**
  `https://kristianedu.github.io/calendario-mundial/mundial_2026_dinamico.ics`

## 🛠 Arquitectura y Funcionamiento

### Calendario en vivo
1. `base_mundial.ics`: Contiene todos los partidos programados originales sin marcadores.
2. `generador.py`: El script en Python que revisa la hora actual, la cruza con el horario de `base_mundial.ics`, y si hay partido activo, se conecta a la API de `football-data.org` para bajar los marcadores.
3. `.github/workflows/en_vivo.yml`: El robot (GitHub Action) que arranca cada 5 minutos, ejecuta el script, y publica el nuevo `.ics` en la rama `gh-pages`.

### Otros componentes
- `actualizar_cuotas.py` (workflow `cuotas.yml`): Consulta `The Odds API` cada 2 horas y añade las cuotas promedio de cada partido al calendario.
- `actualizar_clasificados.py` (workflow `clasificados.yml`): Se ejecuta a diario para actualizar los equipos clasificados a la fase eliminatoria.
- `generar_bracket.py` + `bracket.html`: Generan el bracket visual de la fase eliminatoria, publicado en la rama `gh-pages`.
- `notificar_whatsapp.py`: Cuando finaliza un partido, captura una imagen del bracket con Playwright y la envía a grupos de WhatsApp mediante Green API. Requiere los secrets `GREENAPI_ID`, `GREENAPI_TOKEN` y `WHATSAPP_GROUP_ID`.

## ⚙️ Cómo replicarlo (Para Desarrolladores)
Si quieres usar este repositorio para ti mismo:
1. Haz un **Fork** de este repositorio.
2. Crea una cuenta gratuita en [football-data.org](https://www.football-data.org/client/register).
3. Copia tu `API Key`.
4. En tu GitHub, ve a **Settings > Secrets and variables > Actions**.
5. Crea un Secret llamado `API_KEY` y pega ahí tu llave.
6. (Opcional) Para las cuotas de apuestas, crea una cuenta en [The Odds API](https://the-odds-api.com/) y guarda tu llave en un Secret llamado `ODDS_API_KEY`.
7. (Opcional) Para las notificaciones de WhatsApp, crea los Secrets `GREENAPI_ID`, `GREENAPI_TOKEN` y `WHATSAPP_GROUP_ID` con tus credenciales de Green API.
8. Habilita GitHub Pages en tu repositorio desde **Settings > Pages** seleccionando la rama `gh-pages`.

¡Que ruede el balón! ⚽🌍
