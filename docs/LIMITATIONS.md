# Limitations and Honest Scope

## Data limitations

The supplied Unihack catalog is a raw input dataset. It does not provide official expected output for each product. Consequently, the platform does not claim ground-truth accuracy, field-level expected-value accuracy, or benchmark performance.

Official Delivery Format details, complete LOV registries, complete UOM registries, and field-specific character-limit matrices are not assumed. The system uses only reference artifacts that are actually imported and reports unsupported validation as unavailable or not evaluated.

## Discovery limitations

Controlled discovery supports safe, identity-verified evidence handling. An external discovery provider is optional and may be unconfigured. In that state the application reports a safe no-provider status. The system does not fabricate URLs, scrape unverified identity matches, or treat external content as automatically authoritative.

## Automation limitations

Human review remains required for missing critical fields, unresolved conflicts, unsupported reference checks, and other review-required states. The application does not silently rewrite extracted values or automatically resolve conflicting source assertions.

## Model and platform scope

The verified implementation does not include RAG, FAISS, embeddings, a knowledge graph, Random Forest or other ML trust scoring, LangGraph agents, or autonomous multi-step agents. The current intelligence pipeline uses the existing configured LLM-compatible extraction path and deterministic application services around it.

## Deployment limitations

The repository includes production-aware configuration, container startup, health/readiness probes, upload limits, environment-driven API configuration, Vercel-oriented frontend configuration, and documentation. Actual cloud deployment still requires operator-provided infrastructure, database, storage, domain, CORS origins, and secrets.

## Evaluation language

Rule-based quality metrics describe compliance with available rules and references. They must not be called ground-truth accuracy. A confidence score describes evidence strength or extraction confidence; it is not a statistical correctness guarantee.
