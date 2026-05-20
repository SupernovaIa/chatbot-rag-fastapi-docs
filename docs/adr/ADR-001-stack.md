# ADR-001: Stack del proyecto bajo restricción cero tarjeta

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** stack, foundational

## Contexto y problema

El proyecto es un caso práctico didáctico que debe poder reproducir cualquier alumno sin entregar datos bancarios. Esto restringe el stack: nada que requiera tarjeta, todo lo emulable corre en local.

## Drivers de la decisión

- Cero tarjeta para el alumno.
- Patrón canónico de RAG en producción.
- Una sola fuente de complejidad LLM (un proveedor) para reducir variables.
- Stack que se asemeje al de producción gestionada para que el alumno transfiera el aprendizaje.

## Opciones consideradas

- A. Stack 100% local con modelos open en Ollama.
- B. Stack local con Gemini free tier como único proveedor LLM.
- C. Stack mixto con Anthropic/OpenAI APIs (requiere tarjeta).

## Decisión

Opción B. Una API key de Google AI Studio cubre embeddings (`gemini-embedding-001`), generación (Gemini Flash), juez (Gemini Pro), reranker y guardrail. Vector store y observabilidad en local (pgvector, Phoenix self-host). Object storage emulado con Azurite.

Se fija el *tier* del modelo, no la versión exacta: la familia Gemini evoluciona rápido. Al construir el repo se ancla el ID del modelo vigente y se anota la fecha. **Default verificado 2026-05-20:** Gemini 3.5 Flash (generación/reranker/guardrail), Gemini 3 Pro (juez; 3.5 Pro al salir). Requisito invariante: free tier disponible.

## Consecuencias

### Positivas

- Cero tarjeta cumplido.
- Una sola API key.
- Patrón emulator-first (Azurite) reutilizable.

### Negativas

- Dependencia en Google: rate limits del free tier y políticas de uso.
- Calidad del rerank con Gemini Flash menor que con Cohere Rerank 3.5.

## Alternativas descartadas

- Ollama local: descartado por requerir GPU/CPU del alumno con recursos.
- Anthropic/OpenAI: descartado por requerir tarjeta.
