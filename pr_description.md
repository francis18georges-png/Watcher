Ajoute :
- Un scraper asynchrone respectueux (robots.txt, rate-limit, cache).
- Un store d'embeddings minimal (fake_encoder placeholder).
- Un skeleton RAG minimal avec fake_llm.
- Configuration settings.toml et test smoke pour le scraper.

Notes / TODO :
- Remplacer fake_encoder/fake_llm par adaptateurs réels (sentence-transformers / OpenAI).
- Intégrer FAISS / Pinecone selon besoin pour la production.
- Ne pas lancer scraping massif avant d'avoir whitelist/blacklist, sandbox d'exécution et revue d'éthique.
