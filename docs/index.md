# Documentation Watcher

Bienvenue dans l'espace de référence du projet **Watcher**, l'atelier local d'IA de programmation autonome
axé sur la traçabilité et la sécurité des runs.

!!! abstract "Ce que couvre cette documentation"
    *Architecture* : comment l'orchestrateur, les agents et les ressources partagées coopèrent.
    *Sécurité* : quelles menaces sont prises en compte, comment elles sont détectées et atténuées.
    *Opérations* : les conventions de logging, la feuille de route et les politiques de contribution.

## Structure de la documentation

| Section | Contenu | Points clés |
| --- | --- | --- |
| [Architecture](architecture.md) | Description des composants principaux, flux d'exécution et interfaces. | Diagrammes Mermaid & PlantUML pour visualiser l'orchestrateur et ses dépendances. |
| [Sécurité et conformité](threat-model.md) | Modèle de menaces, scénarios d'incident et charte éthique. | Tableaux de risques, diagrammes de mitigation et procédures de réponse. |
| [Exploitation](logging.md) | Conventions de journalisation, feuille de route et politique de merge. | Référentiel des pratiques d'exploitation et du suivi projet. |

!!! tip "Astuces de navigation"
    - Utilisez ++Ctrl+K++ / ++Cmd+K++ pour ouvrir la recherche instantanée du thème Material.
    - Les onglets du bandeau supérieur regroupent Architecture, Sécurité et Exploitation.
    - Les diagrammes sont interactifs : survolez les nœuds Mermaid pour afficher les détails.

## Architecture en bref

- **Orchestrateur** : modules `app.core` (planner, learner, pipeline) qui synchronisent agents et tâches.
- **Agents spécialisés** : `app.agents` et `app.tools` fournissent génération, évaluation et actions système.
- **Mémoire vectorielle** : `app.core.memory.Memory` et `app.embeddings` conservent les contextes durables.
- **Observabilité** : `app.core.logging_setup` diffuse les journaux structurés et `metrics/` stocke les mesures.

Le [document d'architecture](architecture.md) fournit des vues d'ensemble et des diagrammes séquentiels pour
suivre chaque interaction.

## Sécurité en bref

- **Hypothèses** : fonctionnement majoritairement hors-ligne, dépendances versionnées et environnements isolés.
- **Actifs critiques** : jeux de données DVC, mémoire vectorielle, scripts d'orchestration et journaux d'audit.
- **Mesures** : contrôles CI (`nox`, `bandit`, `mypy`), rotation des journaux, politiques de fusion et charte éthique.

Consultez le [modèle de menaces](threat-model.md) pour la cartographie complète et les plans de réponse.

## Prévisualiser la documentation localement

```bash
pip install -r requirements-dev.txt
mkdocs serve
```

La commande `mkdocs serve` démarre un serveur de développement à `http://127.0.0.1:8000` avec rechargement à
chaud lorsque les fichiers Markdown sont modifiés.
