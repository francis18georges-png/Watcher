# ROADMAP — Watcher comme IA locale à apprentissage continu

## Résumé exécutif

Watcher n’est plus pensé seulement comme un assistant local avec RAG.
La nouvelle direction produit est la suivante :

- devenir une **IA locale offline-first**,
- apprendre **de manière continue** par découverte, scrap ciblé et ingestion surveillée,
- devenir progressivement meilleure **en programmation**,
- devenir progressivement meilleure pour **comprendre les demandes utilisateur**,
- améliorer ses connaissances et ses comportements **sans autonomie incontrôlée**.

Le projet doit évoluer d’un assistant documentaire vers un **système d’apprentissage continu contrôlé**.

La boucle cible est :

**découverte → collecte → extraction → vérification → ingestion → évaluation → promotion**

---

## Principes directeurs

1. **Offline-first par défaut**
   - Toute capacité doit rester utile hors ligne.
   - Le réseau reste exceptionnel, borné et journalisé.

2. **Connaissance en trois états**
   - **Brut** : contenu collecté mais non fiable.
   - **Validé** : contenu vérifié, dédupliqué, scoré et traçable.
   - **Promu** : contenu autorisé pour la réponse, la planification et l’amélioration du système.

3. **Programmation d’abord**
   - La première spécialité de Watcher est la programmation :
     lecture de docs, compréhension de code, correction, tests, refactoring, patchs minimaux, qualité, sécurité, compatibilité.

4. **Compréhension de la demande ensuite**
   - La seconde spécialité est l’interprétation correcte des demandes :
     intention, contraintes, livrable attendu, niveau d’urgence, implicites.

5. **Évaluation avant promotion**
   - Une connaissance nouvelle ne doit pas être promue parce qu’elle existe.
   - Elle doit être promue parce qu’elle **améliore réellement** les résultats sans créer de régression.

6. **Auto-amélioration surveillée**
   - Le système peut proposer des changements sur lui-même.
   - Il ne modifie jamais librement son propre noyau sans :
     sandbox, tests, benchmark, validation, possibilité de rollback.

---

## Diagnostic de départ

### Fondations déjà présentes
- socle local offline-first,
- CLI stable (`init`, `run --offline`, `ask`, `ingest`),
- couche `autopilot`,
- `policy.yaml`,
- mémoire/document store local,
- CI/CD et quality gates,
- documentation technique existante,
- tests nombreux.

### Écarts bloquants à fermer d’abord
- cohérence Python packaging / CI / README,
- contrat CLI ↔ policy,
- options CLI encore no-op,
- application runtime complète de la policy,
- architecture documentaire encore incomplètement alignée sur le code réel,
- roadmap produit encore trop générique.

---

## Architecture cible

### 1. Source Registry
Référentiel des sources autorisées :
- domaine,
- type de source,
- priorité,
- licence,
- niveau de confiance,
- fréquence de rafraîchissement,
- contraintes d’accès.

### 2. Fetch Layer
Collecte contrôlée :
- respect policy,
- quotas,
- cache,
- versioning,
- robots,
- journalisation,
- révocation.

### 3. Extraction Layer
Transformation du contenu en unités utiles :
- faits,
- procédures,
- exemples,
- changements de version,
- erreurs fréquentes,
- compatibilités,
- contre-exemples.

### 4. Verification Layer
Validation avant ingestion :
- corroboration multi-source,
- déduplication,
- scoring,
- détection de contradictions,
- rejet automatique du bruit.

### 5. Knowledge Layers
Stockage séparé :
- brut,
- validé,
- promu,
- échecs / contradictions,
- playbooks réutilisables.

### 6. Evaluation Harness
Mesure de l’amélioration :
- benchmarks code,
- compréhension de demande,
- discipline/sécurité,
- non-régression.

### 7. Safe Self-Improvement Loop
Boucle encadrée :
- proposition,
- patch,
- sandbox,
- tests,
- benchmark,
- promotion ou rollback.

---

## Phases

## Phase 0 — Alignement des fondations

### Objectif
Fermer les contradictions qui empêchent une trajectoire propre.

### Livrables
- vérité Python unifiée,
- contrat CLI/policy corrigé,
- suppression ou implémentation réelle des options no-op,
- policy runtime auditée et appliquée de façon cohérente,
- README et docs réalignés sur l’état réel du dépôt.

### Dépendances
Aucune.

### Critères de réussite
- aucune contradiction visible entre packaging, CI et documentation,
- `watcher policy approve` fonctionne proprement,
- aucun argument utilisateur n’est accepté silencieusement sans effet,
- les invariants offline-first restent intacts.

### Risques
- corrections éparses sans vision d’ensemble,
- dette documentaire qui masque l’état réel du système.

---

## Phase 1 — Apprentissage documentaire contrôlé

### Objectif
Construire la première boucle complète :
**source autorisée → collecte → extraction → vérification → ingestion → promotion/rejet**

### Livrables
- registre de sources autorisées,
- séparation explicite **brut / validé / promu**,
- métadonnées d’ingestion enrichies,
- scoring et corroboration consolidés,
- premiers critères automatiques de promotion,
- premiers rapports d’ingestion exploitables.

### Dépendances
Phase 0.

### Critères de réussite
- chaque connaissance stockée est traçable,
- chaque connaissance promue a un motif de promotion,
- le système sait rejeter ou marquer comme douteux une information insuffisamment corroborée,
- le mode offline reste la norme hors fenêtres réseau.

### Premier slice désormais en place
- registre de sources minimal explicite,
- états `raw / validated / promoted` présents dans le code,
- motifs explicites de validation / promotion et comptage de corroboration persistés,
- premier gate d'évaluation `promote/reject` branché avant ingestion,
- métadonnées minimales branchées sur le flux existant `discover -> verify -> evaluate -> ingest`,
- persistance locale simple, compatible avec l'approche offline-first,
- support GitHub ciblé pour releases, changelogs, docs limitées et fichiers de référence explicitement autorisés.

### Risques
- accumulation de texte non structuré,
- confusion entre mémoire brute et mémoire fiable,
- croissance du corpus sans gain de compétence réel.

---

## Phase 2 — Spécialisation en programmation

### Objectif
Faire de Watcher un système progressivement meilleur pour les tâches de programmation.

### Livrables
- corpus prioritaire de sources techniques fiables :
  docs officielles, changelogs, références API, ressources GitHub ciblées,
- extraction spécialisée programmation :
  procédures, exemples minimaux, incompatibilités de versions, patterns de patchs,
- évaluations programmation :
  bugfix, ajout de tests, explication de tracebacks, migration d’API, refactoring minimal,
- mémoire de patterns réussis / échoués.

### Dépendances
Phases 0 et 1.

### Critères de réussite
- amélioration mesurable sur un lot de tâches de programmation,
- capacité à produire des correctifs plus précis et mieux justifiés,
- réduction des erreurs de compréhension de docs/API.

### Risques
- sur-spécialisation à un corpus trop étroit,
- récupération de bruit depuis GitHub sans validation suffisante,
- confusion entre exemple de code et vérité générale.

---

## Phase 3 — Compréhension des demandes utilisateur

### Objectif
Améliorer l’interprétation de la demande avant la réponse.

### Livrables
- représentation interne de la demande :
  objectif principal, contraintes, livrable attendu, implicites, niveau d’incertitude,
- évaluations dédiées à la compréhension,
- mécanisme de reformulation interne avant action,
- mémoire de motifs de demandes récurrentes.

### Dépendances
Phases 0, 1 et 2.

### Critères de réussite
- meilleure extraction de l’intention réelle,
- moins de réponses “à côté”,
- meilleure hiérarchisation entre correction urgente, amélioration structurelle et optimisation secondaire.

### Risques
- ajouter de la complexité sans mesures fiables,
- mélanger compréhension de la demande et génération de réponse.

---

## Phase 4 — Auto-amélioration surveillée

### Objectif
Permettre au système de contribuer à sa propre amélioration sans autonomie incontrôlée.

### Livrables
- mécanisme de proposition de patchs,
- sandbox dédiée à l’auto-amélioration,
- tests + benchmarks obligatoires avant promotion,
- journal des changements proposés / rejetés / promus,
- stratégie de rollback.

### Dépendances
Phases 0 à 3.

### Critères de réussite
- aucun changement du système n’est promu sans validation,
- les améliorations proposées augmentent réellement les scores ou réduisent les erreurs,
- les régressions sont détectées et annulables.

### Risques
- auto-modification trop précoce,
- promotion de changements locaux qui dégradent le système global,
- confusion entre apprentissage documentaire et modification du code source.

---

## Ce qui n’est pas prioritaire maintenant

Les sujets suivants sont utiles, mais ne doivent pas redevenir l’axe principal avant que la boucle d’apprentissage soit réelle :

- optimisation base de données,
- cache généralisé,
- extension plugins “pour plus tard”,
- monitoring plus large sans nouveaux signaux métier,
- autonomie multi-domaines trop tôt,
- accès web trop large.

---

## Les 10 priorités absolues

1. Unifier la vérité Python.
2. Corriger définitivement le contrat CLI ↔ policy.
3. Supprimer ou implémenter les paramètres CLI no-op.
4. Appliquer réellement toute la policy runtime.
5. Créer la séparation brut / validé / promu.
6. Définir un registre de sources autorisées.
7. Enrichir l’ingestion avec métadonnées et traçabilité.
8. Construire les premières évaluations de programmation.
9. Construire les premières évaluations de compréhension de la demande.
10. Encadrer l’auto-amélioration par tests, benchmark et rollback.

---

## Définition de réussite du projet

Watcher est considéré aligné avec cette roadmap quand :

- il apprend à partir de sources autorisées,
- il distingue connaissance brute, validée et promue,
- il devient mesurablement meilleur en programmation,
- il comprend mieux ce qu’on lui demande,
- il reste offline-first,
- il n’améliore son propre système que sous contrôle strict.
