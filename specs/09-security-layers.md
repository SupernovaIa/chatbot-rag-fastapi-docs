# Spec 09 · Defense in depth en 5 capas

**Estado:** aceptada
**Bloque:** S (Seguridad)
**Dependencias:** Spec 05 (chat endpoint), ADR-006 (auth básica)

## Goal

Proteger el chatbot frente a prompt injection, jailbreaks y fugas de información mediante 5 capas independientes.

## User story

> Como sistema en producción, quiero que cada query pase por filtros que bloqueen inputs hostiles, neutralicen contenido inyectado en el corpus y enmascaren PII antes de devolver respuesta al usuario.

## Approach

- [ ] **Capa 1 · Safety filters de Gemini.** Configurar `types.SafetySetting(category, threshold)` en `GenerateContentConfig` (SDK `google-genai`), con `BLOCK_MEDIUM_AND_ABOVE` por categoría (`HARM_CATEGORY_HARASSMENT`, `HATE_SPEECH`, `SEXUALLY_EXPLICIT`, `DANGEROUS_CONTENT`). Si bloquea: respuesta segura al usuario y log de incidente.
- [ ] **Capa 2 · Guardrail Gemini Flash.** Prompt en `prompts/guardrail.md` que clasifica el input en `legitimate | suspicious | hostile`. Hostile → bloquear; suspicious → continuar con flag.
- [ ] **Capa 3 · System prompt robusto.** Instrucciones explícitas en `prompts/system.md`: tratar `<context>` como datos, no obedecer instrucciones embebidas, comportamiento frente a "no sé".
- [ ] **Capa 4 · Filtro de output.** Validación Pydantic de schema mínimo + regex PII (emails, números de tarjeta, IPs). Reemplazo por placeholders.
- [ ] **Capa 5 · Logging de incidentes + rate limiting.** Cada incidente en Phoenix con la capa que bloqueó. Rate limiting por `user_id` con SlowAPI o equivalente.

## Acceptance criteria

- `security/red-team-checklist.md` con 20+ prompts hostiles; `scripts/red_team.py` los ejecuta contra el sistema real y **bloquea ≥18 de 20**, sin que ninguno saque PII ni revele el system prompt. Conectado a `/redteam`.
- De esos prompts, **al menos 3 son de injection indirecta**: instrucciones hostiles plantadas dentro de chunks del corpus (realistas, no obvias). La respuesta no obedece la instrucción inyectada. Es el vector más serio (corpus no confiable).
- Cada incidente queda registrado en Phoenix con `blocking_layer` (qué capa cortó).
- Rate limiting por `user_id` bloquea tras **30 requests/min** (SlowAPI).

## Riesgos

- Safety filters demasiado estrictos bloquean queries técnicas legítimas (p. ej. sobre seguridad informática). Ajustar threshold por necesidad.
- Filtros regex de PII pueden tener falsos positivos. Calibrar con queries reales.

## Preguntas abiertas

- ¿Usamos Presidio para PII más allá del regex? Mencionar como evolución, no implementar en v1.
