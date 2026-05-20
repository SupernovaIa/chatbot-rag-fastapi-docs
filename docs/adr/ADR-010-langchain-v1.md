# ADR-010: LangChain v1 + langchain-google-genai como framework

**Estado:** aceptado
**Fecha:** 2026-05-20
**Tags:** framework, dependencies

## Contexto

Necesitamos un framework para orquestar el pipeline RAG (loaders, splitters, embeddings, retrievers, generación). Alternativas: LangChain, LlamaIndex, SDK directo de Google GenAI.

## Drivers

- Abstracción probada con documentación.
- Fácil cambiar de proveedor más adelante.
- Integración con Google AI Studio.
- Compatibilidad con LangGraph para un agente con tool use más adelante.

## Opciones

- A. LangChain v1 + langchain-google-genai.
- B. LlamaIndex.
- C. SDK directo de Google GenAI sin framework.

## Decisión

Opción A. LangChain v1 (octubre 2025) con langchain-google-genai como integración con Gemini.

## Consecuencias

### Positivas

- Abstracciones de loaders, splitters, retrievers ya implementadas.
- Misma base que LangGraph para un agente con tool use más adelante.
- Cambiar de Google a otro proveedor LLM en el futuro es trivial.

### Negativas

- Curva de aprendizaje de LangChain. El alumno ya conoce básicos del programa.
- Algunas abstracciones LangChain son verbosas para casos simples.

## Alternativas descartadas

- LlamaIndex: especializado en Document QA, menos genérico cuando el sistema crece a agentes.
- SDK directo: control total pero hay que escribir loaders, splitters, retrieval orchestration desde cero.

## Notas

- Usar `create_agent` y LangGraph en futuro, no el `AgentExecutor` legacy.
- Pin de versión de LangChain v1.x en `pyproject.toml` para evitar breaking changes accidentales antes de v2.
