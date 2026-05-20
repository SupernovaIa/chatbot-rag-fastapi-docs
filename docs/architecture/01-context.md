# C4 Level 1 · System Context

> Vista de máximo nivel: el chatbot RAG y los sistemas con los que interactúa.

## Diagrama

```mermaid
C4Context
  title System Context · Chatbot RAG sobre FastAPI docs

  Person(user, "Usuario", "Persona que consulta el chatbot")
  Person(admin, "Operador", "Mantiene el corpus, revisa trazas y métricas")

  System(chatbot, "Chatbot RAG", "Responde preguntas sobre FastAPI docs con citas verificables")

  System_Ext(google, "Google AI Studio", "Gemini Flash, Gemini Pro, gemini-embedding-001")
  System_Ext(github, "GitHub", "Repositorio del código, CI con GitHub Actions, secrets")

  Rel(user, chatbot, "Pregunta sobre FastAPI", "HTTPS, multi-turn")
  Rel(admin, chatbot, "Indexa corpus, revisa trazas, ejecuta evals")

  Rel(chatbot, google, "Embeddings, generación, reranking, evals", "HTTPS")
  Rel(chatbot, github, "Push, PRs, Actions con eval gate", "HTTPS")

  UpdateRelStyle(user, chatbot, $offsetY="-20")
  UpdateRelStyle(admin, chatbot, $offsetY="20")
```

## Actores

- **Usuario:** consume el chatbot vía interfaz web. Hace login y mantiene conversaciones multi-turno sobre las docs de FastAPI.
- **Operador:** mantiene el sistema. Indexa el corpus, revisa el dashboard de Phoenix, ejecuta el dataset gold cuando hay cambios y revisa los logs de incidentes de seguridad.

## Sistemas externos

- **Google AI Studio:** único proveedor LLM. Una sola API key cubre embeddings (`gemini-embedding-001`), generación (Gemini Flash), juez de evals (Gemini Pro), reranking y guardrail.
- **GitHub:** alojamiento del código y CI/CD con eval gate.

## Decisiones clave a nivel de sistema

- **Cero terceros LLM más allá de Google.** No hay Anthropic, OpenAI ni Cohere en el camino crítico. Decisión por restricción de cero tarjeta.
- **Sin proveedor de auth externo.** Auth local con FastAPI Users + bcrypt + JWT.
- **Sin observabilidad externa.** Phoenix self-host, no LangSmith ni Datadog.
