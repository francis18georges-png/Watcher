# Architecture

Watcher orchestre plusieurs briques spécialisées pour fournir un atelier d'IA local, sûr et traçable. Cette page
présente les responsabilités de chaque composant et illustre les principaux échanges via des diagrammes Mermaid et
PlantUML intégrés à la documentation.

## Vue générale

- **Interface utilisateur** : scripts CLI (`python -m app.ui.main`) et automatisations (`run.ps1`) qui déclenchent les
  scénarios d'entraînement ou d'évaluation.
- **Orchestrateur** : modules `app.core` responsables de la planification des tâches, de l'exécution des agents et du
  pilotage du curriculum adaptatif.
- **Agents et outils** : classes sous `app.agents` et `app.tools` chargées de la génération de code, de l'analyse et de la
  rétroaction utilisateur.
- **Mémoire vectorielle** : stockage persistant des connaissances et contextes dans `app.core.memory`.
- **Qualité et sécurité** : bancs d'essai (`tests/`, `metrics/`, `QA.md`) et garde-fous (`bandit.yml`, `pyproject.toml`).
- **Journalisation** : configuration centralisée via `app.core.logging_setup` pour tracer toutes les décisions et actions.

## Diagramme d'ensemble (Mermaid)

```mermaid
flowchart LR
    subgraph Client
        User[Utilisateur]
        CLI[CLI & scripts]
    end

    subgraph Orchestration
        Core[Orchestrateur]
        Curriculum[Curriculum adaptatif]
        Plugins[Gestion des plugins]
    end

    subgraph Execution
        Agents[Agents spécialisés]
        Tools[Outils & exécutants]
    end

    subgraph DataLayer[Persistance]
        Memory[(Mémoire vectorielle)]
        Datasets[(Datasets DVC)]
        Logs[(Journal JSON)]
    end

    subgraph Assurance
        QA[Benchmarks & QA]
        Security[Garde-fous sécurité]
    end

    User --> CLI --> Core
    Core --> Curriculum
    Core --> Plugins
    Core --> Agents
    Agents --> Tools
    Agents --> QA
    QA --> Core
    Agents --> Memory
    Tools --> Memory
    Memory --> Agents
    Core --> Logs
    Security --> Core
    Security --> QA
    Datasets --> Agents
    Agents --> Datasets
```

Le diagramme met en évidence la boucle de rétroaction : les agents consultent la mémoire vectorielle, exécutent des
outils puis alimentent les bancs d'essai et les journaux. Les résultats réinjectés dans l'orchestrateur lui permettent
d'affiner la stratégie d'entraînement.

## Interactions détaillées (PlantUML)

```plantuml
@startuml
skinparam componentStyle rectangle
skinparam shadowing false

actor Utilisateur as User

package "Watcher" {
  [Interface CLI] as CLI
  [Orchestrateur] as Orchestrator
  [Gestion des plugins] as Plugins
  [Curriculum adaptatif] as Curriculum
  [Mémoire vectorielle] as VectorStore
  [Qualité & sécurité] as Quality
  [Bus d'événements] as EventBus
}

User --> CLI : Configure & lance les runs
CLI --> Orchestrator : Commandes
Orchestrator --> Plugins : Découverte & exécution
Orchestrator --> Curriculum : Mise à jour des objectifs
Orchestrator --> VectorStore : Lecture/écriture de contexte
Orchestrator --> Quality : Benchmarks & garde-fous
Quality --> Orchestrator : Rapports
VectorStore --> Plugins : Fournit le contexte
Quality --> EventBus : Alertes
EventBus --> Orchestrator : Décisions automatisées
@enduml
```

Cette vue composant détaille les principaux flux applicatifs et souligne l'importance de la modularité : chaque brique
peut être remplacée ou étendue sans casser la chaîne de valeur si les interfaces documentées sont respectées.

## Chaîne d'observabilité

```mermaid
sequenceDiagram
    autonumber
    participant Agent
    participant Logger
    participant Sink as Stockage (JSON)
    participant Monitor as Tableau de bord

    Agent->>Logger: événement(structuré)
    Logger-->>Sink: append log
    Sink-->>Monitor: export métriques
    Monitor-->>Agent: feedback sur dérives
```

Cette séquence illustre comment les événements structurés alimentent la surveillance. La journalisation JSON autorise
l'export vers des tableaux de bord tout en conservant la traçabilité locale.

## Points d'extension

- **Plugins** : `plugins.toml` et les entry points `watcher.plugins` permettent d'ajouter des capacités sans modifier le
  noyau.
- **Pipelines de qualité** : de nouveaux scénarios peuvent être ajoutés dans `tests/` ou `metrics/` pour renforcer les
  contrôles.
- **Sources de données** : les ensembles DVC sous `datasets/` peuvent être étendus avec de nouveaux corpus tout en
  conservant la reproductibilité.
