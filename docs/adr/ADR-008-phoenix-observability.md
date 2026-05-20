# ADR-008: Arize Phoenix self-host como herramienta de observabilidad

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** observability

## Contexto

Necesitamos trazas por query con spans por fase (rewrite, retrieve, rerank, generate), latencia, coste estimado y consumo por usuario. Bajo restricción cero tarjeta y con identidad "todo local", evaluamos opciones.

## Drivers

- Trazas específicas para apps con LLM (no solo APM genérico).
- Footprint ligero en el portátil del alumno (que arranque en cualquier máquina).
- Local, sin cuenta cloud ni datos saliendo de la máquina.
- Free y open source.
- Instrumentación nativa de LangChain.

## Opciones

- A. Arize Phoenix self-host (un contenedor, OpenTelemetry/OpenInference).
- B. Langfuse Cloud (Hobby free tier, sin tarjeta).
- C. Langfuse v3 self-host (web + worker + Postgres + ClickHouse + Redis + S3).
- D. Logs estructurados sin tool específica.

## Decisión

Opción A. Phoenix self-host en un único contenedor (`arizephoenix/phoenix`, UI y colector OTLP en el puerto 6006), con persistencia en volumen propio.

El backend instrumenta con OpenTelemetry + OpenInference para LangChain, exportando spans al colector de Phoenix vía `PHOENIX_COLLECTOR_ENDPOINT`. Sin API keys: el Phoenix local no requiere autenticación.

## Consecuencias

### Positivas

- Cero coste, cero tarjeta, datos locales.
- Un solo contenedor: el stack arranca en portátiles modestos.
- Spans por fase con instrumentación nativa de LangChain (OpenInference).
- Open source (ELv2): control total.
- Estándar OpenTelemetry: la instrumentación es portable a otros backends.

### Negativas

- Un contenedor extra en el docker-compose y su volumen.
- Recursos locales del alumno: memoria adicional moderada del servicio Phoenix.

## Alternativas descartadas

- **Langfuse v3 self-host:** v3 (estable y productivo desde diciembre de 2024) migró las trazas a ClickHouse e introdujo worker, Redis y almacén S3. Self-hostearlo añade ~6 contenedores y eleva el requisito de RAM a ~12 GB, desproporcionado para el objetivo didáctico y con riesgo de que el alumno no levante el stack.
- **Langfuse Cloud (Hobby):** válido y sin tarjeta (50k unidades/mes), pero saca las trazas a un servicio externo sin necesidad, rompiendo la identidad "todo local" del proyecto.
- **Logs sin tool:** insuficiente para sistemas LLM, dejan de servir rápido.

## Notas

- RAGAS sigue siendo la herramienta de evals (Bloque E). Phoenix se usa solo para tracing, aunque trae evaluadores propios.
- En migración a Azure (v1.1), considerar Phoenix en Container App o un backend OTLP gestionado; al ser estándar OpenTelemetry, el cambio es de configuración del exportador.
