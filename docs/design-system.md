# Sistema de diseño del frontend

Criterios de diseño para la UI del chatbot (bloque D). Independiente del material didáctico: este es el sistema del producto. La skill `ui-ux-pro-max` debe ejecutar **este** estilo, no improvisar uno.

## Principio

UI minimal, estética de asistente de documentación. El foco del proyecto es el pipeline RAG, no el front. El diseño cuida legibilidad, accesibilidad y los estados del chat (loading, streaming, error), sin inflar componentes.

## Paleta

Variables CSS a definir en el frontend:

```css
:root {
  --bg: #FFFFFF;        /* fondo app */
  --fg: #1C3C42;        /* texto principal */
  --accent: #3A6870;    /* burbuja/acento del asistente */
  --highlight: #82C4AF; /* chips de cita [1] [2] */
  --muted: #8aa4a8;     /* metadata, timestamps */
  --green: #3A9470;     /* estado éxito */
  --danger: #C06060;    /* estado error */
  --orange: #D4825A;    /* streaming / aviso */
}
```

| Pieza UI | Color |
|---|---|
| Fondo app | `--bg` |
| Texto principal | `--fg` |
| Burbuja y acento del asistente | `--accent` |
| Chips de cita `[1] [2]` clicables | `--highlight` |
| Metadata, timestamps | `--muted` |
| Estado éxito | `--green` |
| Estado error | `--danger` |
| Indicador de streaming / aviso | `--orange` |

## Tipografía

- **Interfaz y texto:** Poppins (Google Fonts, pesos 400/500/600).
- **Código en respuestas y snippets:** JetBrains Mono. Las respuestas citan docs de FastAPI con código, así que el render Markdown debe usar la monoespaciada para bloques y código inline.

## Componentes y comportamiento

- **Burbujas:** asistente alineado a la izquierda con acento `--accent`; usuario a la derecha con fondo suave.
- **Citas:** chips `[1] [2]` con color `--highlight`, clicables, que abren el chunk original recuperado.
- **Estados del chat (obligatorios):**
  - *loading:* antes del primer token.
  - *streaming:* indicador con `--orange` mientras llegan tokens (SSE).
  - *error:* mensaje con `--danger` si la respuesta falla.
- **Accesibilidad:** contraste mínimo AA, focus states visibles en todos los interactivos (chips, botones, input), navegable por teclado.

## Uso con la skill

Al invocar `ui-ux-pro-max` en el bloque D, pásale este fichero como criterios. La skill aplica accesibilidad, estados y layout sobre esta paleta y tipografía; no elige estilo nuevo.
