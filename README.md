# Watcher

![Benchmark status badge](metrics/performance_badge.svg)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/<owner>/Watcher/badge)](https://securityscorecards.dev/viewer/?uri=github.com/<owner>/Watcher)

Atelier local d'IA de programmation autonome (offline par défaut).
Mémoire vectorielle, curriculum adaptatif, A/B + bench et quality gate sécurité.

## Version

La dernière version stable est **v0.4.0** (tag `v0.4.0`, publiée le 20 septembre 2025).

- 📦 Téléchargement direct : [https://github.com/<owner>/Watcher/releases/tag/v0.4.0](https://github.com/<owner>/Watcher/releases/tag/v0.4.0)
- 🗒️ Notes complètes : voir le [CHANGELOG](CHANGELOG.md) et la [page de notes de version](docs/release_notes.md).
- ✅ Instructions de vérification (signatures, provenance, empreintes) : détaillées ci-dessous pour chaque
  artefact publié.

## Citer Watcher

Merci de citer ce dépôt lorsque vous réutilisez son code, ses jeux de données ou sa
documentation. Les métadonnées officielles de citation sont fournies dans
[`CITATION.cff`](CITATION.cff) et peuvent être exportées dans différents formats à
l'aide de [`cffconvert`](https://github.com/citation-file-format/cff-converter-python) :

```bash
pip install cffconvert
cffconvert --validate --format bibtex --outfile watcher.bib
```

## Documentation

La documentation technique est générée avec [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
et publiée via l'environnement **github-pages** du dépôt.
Activez GitHub Pages dans les paramètres du dépôt (source : **GitHub Actions**) puis cliquez sur
« View deployment » depuis l'onglet **Deployments → github-pages** pour accéder au site public généré
par `deploy-docs.yml`.

Pour la prévisualiser localement :

```bash
pip install -r requirements-dev.txt
mkdocs serve
```

Le workflow GitHub Actions [`deploy-docs.yml`](.github/workflows/deploy-docs.yml) construit le site avec `mkdocs build --strict`
avant de le publier sur l'environnement **GitHub Pages** à chaque push sur `main`.

## Sécurité et qualité automatisées

Le badge OpenSSF Scorecard reflète en continu l'état de la posture de sécurité du dépôt
(`.github/workflows/scorecard.yml`). Il est généré à partir de l'API publique
<https://api.securityscorecards.dev/projects/github.com/<owner>/Watcher> et renvoie vers le
rapport détaillé sur <https://securityscorecards.dev>. Un run planifié hebdomadaire publie les
résultats sur le tableau de bord OpenSSF, tandis que chaque Pull Request bénéficie d'une analyse
à jour dans GitHub Actions.

La CI inclut désormais un garde-fou `Scorecard gate` dans [`ci.yml`](.github/workflows/ci.yml)
qui rejoue l'analyse Scorecard à chaque Pull Request. Le job échoue si le score global
redescend sous `7`, empêchant ainsi le reste du pipeline et la fusion tant que les bonnes
pratiques identifiées par Scorecard ne sont pas rétablies.

La matrice Python du même workflow est résolue par le job `determine-python`. En l'absence
de variable `WATCHER_NOX_PYTHON`, il publie explicitement les versions supportées (`3.10`,
`3.11`, `3.12`) afin que les jobs `quality` puissent s'exécuter sur Linux, macOS et Windows
pour chaque interpréteur. Pour cibler un sous-ensemble lors d'un debug ou d'un backport,
exportez `WATCHER_NOX_PYTHON="3.11"` (ou plusieurs valeurs séparées par des virgules) avant
de lancer `nox` ou de déclencher le workflow manuellement ; la même logique s'applique aux
exécutions locales via `noxfile.py`.

## Releases, SBOM et provenance

Chaque tag SemVer (`vMAJOR.MINOR.PATCH`) déclenche le workflow [`release.yml`](.github/workflows/release.yml) qui produit
des exécutables Windows, Linux et macOS, un SBOM CycloneDX par plateforme et une attestation de provenance SLSA niveau 3.

### Artefacts publiés

| Fichier | Description |
| --- | --- |
| [`Watcher-Setup.zip`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/Watcher-Setup.zip) | Archive PyInstaller Windows signée et empaquetée. |
| [`Watcher-Setup.zip.sigstore`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/Watcher-Setup.zip.sigstore) | Bundle Sigstore pour vérifier la signature du binaire Windows (`sigstore verify identity --bundle ...`). |
| [`Watcher-sbom.json`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/Watcher-sbom.json) | Inventaire CycloneDX des dépendances installées pendant le build Windows (`cyclonedx-bom` / `cyclonedx-py`). |
| [`Watcher-linux-x86_64.tar.gz`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/Watcher-linux-x86_64.tar.gz) | Tarball PyInstaller contenant le binaire autonome Linux. |
| [`Watcher-linux-sbom.json`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/Watcher-linux-sbom.json) | SBOM CycloneDX généré lors du build Linux. |
| [`Watcher-macos-x86_64.zip`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/Watcher-macos-x86_64.zip) | Archive PyInstaller macOS signée (si certificat configuré) et soumise à la notarisation Apple lorsque les secrets sont fournis. |
| [`Watcher-macos-sbom.json`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/Watcher-macos-sbom.json) | SBOM CycloneDX généré lors du build macOS. |
| [`Watcher-Setup.intoto.jsonl`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/Watcher-Setup.intoto.jsonl) | Provenance SLSA générée par [`slsa-github-generator`](https://github.com/slsa-framework/slsa-github-generator) (atteste la supply chain du binaire Windows). |
| `watcher-*.whl` / `watcher-*.tar.gz` | Paquets Python (wheel + source) publiés dans la section *Assets* (installables via `pip`). |
| [`pip-audit-report.json`](https://github.com/<owner>/Watcher/releases/download/v0.4.0/pip-audit-report.json) | Rapport JSON de l'analyse `pip-audit` exécutée sur `requirements.txt` et `requirements-dev.txt`. |

### Vérifier les artefacts publiés

Avant toute installation, validez l'authenticité et l'intégrité des binaires téléchargés depuis la
release `v0.4.0` :

```bash
# 1. Télécharger tous les fichiers nécessaires (binaire + SBOM + provenance)
RELEASE="https://github.com/<owner>/Watcher/releases/download/v0.4.0"
wget "$RELEASE/Watcher-Setup.zip" \
     "$RELEASE/Watcher-Setup.zip.sigstore" \
     "$RELEASE/Watcher-Setup.intoto.jsonl" \
     "$RELEASE/Watcher-sbom.json"

# 2. Vérifier la signature Sigstore (Windows)
sigstore verify identity \
  --bundle Watcher-Setup.zip.sigstore \
  --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/v0.4.0" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  Watcher-Setup.zip

# 3. Vérifier la provenance SLSA (attestation supply chain)
slsa-verifier verify-artifact \
  --provenance Watcher-Setup.intoto.jsonl \
  --source-uri github.com/<owner>/Watcher \
  --source-tag v0.4.0 \
  Watcher-Setup.zip

# 4. Calculer/valider les empreintes
sha256sum Watcher-Setup.zip Watcher-linux-x86_64.tar.gz Watcher-macos-x86_64.zip
```

- Pour Linux/macOS, comparez le `sha256sum` obtenu avec les empreintes publiées dans la release.
- Les SBOM (`Watcher-*-sbom.json`) peuvent être explorés avec `jq`, importés dans un scanner CycloneDX ou
  validés via `cyclonedx-py validate Watcher-sbom.json`.
- Les distributions Python (`watcher-*.whl`, `watcher-*.tar.gz`) sont signées par la provenance GitHub
  (workflow `release.yml`) et peuvent être installées via `pip install watcher-*.whl` après vérification des
  `sha256sum`.

Ces fichiers sont publiés en tant qu'artefacts de release. Téléchargez le SBOM correspondant pour auditer les composants de la
plateforme visée et conservez la provenance `*.intoto.jsonl` pour tracer la chaîne de build ou alimenter un vérificateur SLSA.

### Installer sur Windows

1. Téléchargez `Watcher-Setup.zip` ainsi que `Watcher-Setup.zip.sigstore` depuis la page GitHub Releases
   correspondant au tag SemVer (`vMAJOR.MINOR.PATCH`) que vous souhaitez déployer.
2. Installez le CLI [Sigstore](https://www.sigstore.dev/) si nécessaire :

   ```bash
   pip install sigstore
   ```

3. Vérifiez la signature à l'aide du bundle publié par le workflow `release.yml` :

   ```powershell
   sigstore verify identity `
     --bundle Watcher-Setup.zip.sigstore `
     --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/<tag>" `
     --certificate-oidc-issuer https://token.actions.githubusercontent.com `
     Watcher-Setup.zip
   ```

   Remplacez `<owner>` par l'organisation ou l'utilisateur GitHub hébergeant ce dépôt et `<tag>` par la version téléchargée.
   La commande échoue si la signature ne provient pas du workflow officiel exécuté sur GitHub Actions.
4. Extrayez l'archive (clic droit → *Extraire tout...* ou `Expand-Archive` sous PowerShell) puis lancez `Watcher.exe`.
   Conservez le dossier d'extraction tel quel : il contient la configuration (`config/`), les prompts LLM et les fichiers
   auxiliaires (`LICENSE`, `example.env`) nécessaires à l'exécutable.

Le bundle Sigstore fournit également un horodatage de transparence et peut être vérifié hors-ligne grâce au
[`rekor-cli`](https://github.com/sigstore/rekor) si vous devez archiver la preuve de signature.

### Installer sur Linux

1. Téléchargez `Watcher-linux-x86_64.tar.gz` depuis la page GitHub Releases correspondant à la version désirée.
2. Extrayez l'archive dans un répertoire dédié :

   ```bash
   tar -xzf Watcher-linux-x86_64.tar.gz
   ```

3. Exécutez le binaire depuis le dossier extrait :

   ```bash
   cd Watcher
   ./Watcher --help
   ```

   Le bundle contient la configuration et les prompts requis. Vous pouvez déplacer le dossier complet vers un emplacement
   inclus dans votre `PATH` ou créer un lien symbolique vers `Watcher`.

### Installer sur macOS

1. Téléchargez `Watcher-macos-x86_64.zip` depuis la page GitHub Releases.
2. Décompressez l'archive (Finder → *Décompresser* ou `ditto -x -k Watcher-macos-x86_64.zip Watcher`).
3. Si un certificat de signature est configuré, le binaire est signé et le workflow soumet automatiquement l'archive à la
   notarisation Apple à l'aide de `notarytool`. Vous pouvez vérifier l'intégrité locale :

   ```bash
   codesign --verify --deep --strict Watcher/Watcher
   ```

   et afficher le ticket de notarisation (si disponible) via l'artefact de workflow `Watcher-macos-notarization.json` ou en interrogeant
   `xcrun notarytool history --apple-id <id> --team-id <team> --password <app-specific-password>`.
4. Lancez l'exécutable depuis le Terminal :

   ```bash
   cd Watcher
   ./Watcher --help
   ```

   Conservez l'ensemble du dossier, qui regroupe la configuration et les prompts nécessaires. Si aucun certificat n'est fourni,
   macOS affichera un avertissement Gatekeeper ; autorisez l'exécution via *Préférences système → Sécurité et confidentialité*.

## Benchmarks

Le script `python -m app.core.benchmark run` exécute quatre scénarios
représentatifs en mesurant le temps et l'utilisation mémoire via `tracemalloc` :

- `planner_briefing` : génère des briefs successifs avec le planificateur.
- `learner_update` : applique plusieurs mises à jour du `Learner`.
- `metrics_tracking` : exerce les context managers de `PerformanceMetrics`.
- `memory_operations` : manipule la base SQLite de `Memory` (ajout, résumé,
  feedback et recherche vectorielle).

Chaque exécution ajoute une entrée historique dans `metrics/benchmarks.jsonl`,
met à jour le résumé courant dans `metrics/benchmarks-latest.json` et régénère
le badge `metrics/performance_badge.svg`.

Les seuils de non-régression sont définis dans `metrics/bench_thresholds.json`.
Pour vérifier qu'ils sont respectés, utilisez :

```bash
python -m app.core.benchmark run --samples 5 --warmup 1
python -m app.core.benchmark check --update-badge
```

La CI (`ci.yml`) exécute automatiquement ces commandes et échoue si un scénario
dépasse l'un des seuils configurés.

## Gestion des données avec DVC

Watcher versionne ses jeux de données légers avec [DVC](https://dvc.org/).
Installez l'outil (par exemple `pip install "dvc[s3]"`) avant d'exécuter les commandes ci-dessous.

- L'étape `prepare-data` lit `datasets/raw/simple_linear.csv` et génère
  `datasets/processed/simple_linear.csv` en appliquant les hyperparamètres
  définis dans `params.yaml` (`prepare.sample_size`, `prepare.random_seed`).
- L'étape `validate-data` exécute trois scripts (`scripts/validate_schema.py`,
  `scripts/validate_size.py`, `scripts/validate_hash.py`) pour vérifier la
  structure, la taille et l'empreinte MD5 du fichier préparé. Les attentes sont
  décrites dans la section `validate.simple_linear` de `params.yaml`.

Pour régénérer et valider les données locales :

```bash
dvc repro
```

Le dépôt est configuré avec un remote S3 `storage` pointant vers
`s3://watcher-artifacts` (voir `.dvc/config`). Pour publier ou récupérer les
artefacts :

1. Configurer vos identifiants AWS via `aws configure` ou en définissant les
   variables d'environnement `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` et
   `AWS_DEFAULT_REGION`.
2. Initialiser la cible par défaut si nécessaire :

   ```bash
   dvc remote default storage
   ```

3. Synchroniser les données :

   ```bash
   dvc push   # envoie les artefacts locaux vers S3
   dvc pull   # récupère les artefacts manquants depuis S3
   ```

Si vous devez utiliser un autre fournisseur (Azure Blob Storage, Google Cloud,
etc.), ajustez l'URL du remote via `dvc remote modify storage url <nouvelle-url>`
et mettez à jour la configuration d'authentification associée.

## Installation

1. Cloner ce dépôt.
2. Créer et activer un environnement Python 3.10 ou supérieur :

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate   # Windows
   ```

3. Installer les dépendances :

   ```bash
   pip install -r requirements.txt
   ```

   Pour activer les quotas d'exécution sur Windows, installez
   également la dépendance optionnelle `pywin32` :

   ```bash
   pip install pywin32  # facultatif
   ```

4. Installer les outils de développement :

    ```bash
    pip install -r requirements-dev.txt
    ```

    Ce fichier fixe des versions précises afin d'assurer une installation reproductible.

    Sur Windows, le script `installer.ps1` installe automatiquement toutes ces dépendances.

Les fichiers d'environnement (`*.env`), les journaux (`*.log`) et les environnements virtuels (`.venv/`) sont ignorés par Git afin d'éviter la mise en version de données sensibles ou temporaires.

## Exécution via Docker

Une image container officielle est construite par le workflow [`docker.yml`](.github/workflows/docker.yml)
et publiée sur le registre GitHub Container Registry sous `ghcr.io/<owner>/watcher`.

### Utiliser l'image publiée

Les points de montage suivants permettent de persister les fichiers générés par Watcher entre deux
exécutions :

- `/app/data` : base de données principale (`WATCHER_DATABASE__URL`).
- `/app/memory` : cache vectoriel et fichiers de mémoire (`memory/mem.db`).
- `/app/logs` : journaux d'exécution.
- `/app/config` *(optionnel)* : configuration TOML et fichiers `plugins.toml` personnalisés.

```bash
docker run --rm -it \
  -v watcher-data:/app/data \
  -v watcher-memory:/app/memory \
  -v watcher-logs:/app/logs \
  ghcr.io/<owner>/watcher:latest --help
```

Copiez le dossier `config/` du dépôt si vous souhaitez le personnaliser avant de le monter en lecture
(`-v "$(pwd)/config:/app/config:ro"`).  Les variables d'environnement peuvent être fournies avec
`--env-file` (par exemple `--env-file ./example.env`).

Pour exécuter une commande CLI, passez-la directement après l'image :

```bash
docker run --rm -it ghcr.io/<owner>/watcher:latest plugin list
```

### Vérifier les artefacts de signature, de provenance et les SBOM

Le workflow [`docker.yml`](.github/workflows/docker.yml) publie, en plus de l'image container,
les artefacts suivants pour chaque exécution :

- `cosign-bundles/ghcr.io__<owner>__watcher__<tag>.sigstore` : bundle Sigstore de la signature
  keyless pour la référence `ghcr.io/<owner>/watcher:<tag>`.
- `watcher-image-provenance/watcher-image.intoto.jsonl` : attestation SLSA générée via
  [`slsa-github-generator`](https://github.com/slsa-framework/slsa-github-generator) et liée au digest
  publié par le job `Build and publish image`.
- `watcher-image-sbom.cdx.json` : SBOM CycloneDX généré avec `syft`, téléchargeable depuis
  l'artefact `watcher-image-sbom` ou joint à la release correspondante.
- `watcher-image-sbom-spdx/sbom.spdx.json` : SBOM SPDX JSON produit par `syft` pour répondre aux
  exigences de conformité des registres et scanners.

Les caractères `/` et `:` du nom d'image sont remplacés par `__` pour garantir des noms de fichiers
compatibles avec GitHub Actions. Téléchargez l'image, le bundle Sigstore, l'attestation et les SBOM
correspondants au tag SemVer souhaité (`vMAJOR.MINOR.PATCH`), puis vérifiez la signature hors-ligne
avec `cosign` :

```bash
cosign verify \
  --bundle ghcr.io__<owner>__watcher__<tag>.sigstore \
  --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/docker.yml@refs/tags/<tag>" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/<owner>/watcher@sha256:<digest>
```

Remplacez `<tag>` par la version téléchargée (par exemple `v0.4.0`) et `<digest>` par l'empreinte
SHA256 de l'image. Vous pouvez récupérer ce digest via `docker buildx imagetools inspect`
(`docker buildx imagetools inspect ghcr.io/<owner>/watcher:<tag> --format '{{.Digest}}'`).

Pour les images construites depuis `main`, remplacez l'identité du certificat par
`https://github.com/<owner>/Watcher/.github/workflows/docker.yml@refs/heads/main` et utilisez le
digest correspondant (affiché par `docker pull` ou `crane digest`).

L'attestation SLSA permet de relier cryptographiquement ce digest au workflow GitHub Actions.
Téléchargez l'artefact `watcher-image-provenance` puis vérifiez-le avec
[`slsa-verifier`](https://github.com/slsa-framework/slsa-verifier) :

```bash
slsa-verifier verify-image \
  --provenance watcher-image.intoto.jsonl \
  ghcr.io/<owner>/watcher@sha256:<digest>
```

Vous pouvez également inspecter le fichier pour contrôler manuellement les champs `builder.id` et
`buildDefinition.resolvedDependencies` :

```bash
jq '{subject, buildType: .predicate.buildType, builder: .predicate.builder.id}' \
  watcher-image.intoto.jsonl
```

Enfin, examinez les deux SBOM fournis :

```bash
jq '.components[] | {name, version}' watcher-image-sbom.cdx.json | head
jq '.packages[] | {name, versionInfo}' sbom.spdx.json | head
```

Le format CycloneDX reste adapté aux scanners `grype`/`trivy`, tandis que le SBOM SPDX JSON peut être
importé dans des solutions de gouvernance qui n'acceptent que le schéma SPDX 2.3.

### Construire l'image en local

Si vous ne souhaitez pas attendre la publication GitHub Actions, construisez et testez l'image avec Docker :

```bash
docker build -t watcher:local .
docker run --rm -it watcher:local mode offline
```

Les volumes présentés ci-dessus fonctionnent également avec l'image locale (`watcher:local`).

## Environnement de développement

Un dossier `.devcontainer/` est fourni pour disposer d'un environnement prêt à l'emploi
dans VS Code ou GitHub Codespaces. Il utilise l'image Python 3.12 officielle
(le projet restant compatible à partir de Python 3.10), préconfigure les caches
`pip` et `DVC` sur des volumes persistants et installe automatiquement les
dépendances du projet ainsi que les hooks `pre-commit`.

Pour ouvrir le projet dans un devcontainer :

1. Installer l'extension [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).
2. Dans VS Code, exécuter la commande **Dev Containers: Reopen in Container**.
3. Attendre la fin du script `.devcontainer/post-create.sh` qui prépare l'environnement.

Les caches partagés accélèrent notamment les installations pip et la synchronisation DVC
entre plusieurs sessions Codespaces.

## Compatibilité NumPy

Watcher tente d'utiliser la bibliothèque `numpy` lorsqu'elle est disponible.
Si son import échoue, un module de repli léger `numpy_stub` est utilisé à la
place. Les modules Python importent donc `np` via `from app.utils import np`
pour bénéficier automatiquement de ce mécanisme.

## Mémoire et migrations

Le module `Memory` s'appuie sur SQLite et exécute automatiquement les
migrations [Alembic](https://alembic.sqlalchemy.org/) au démarrage pour garantir
la présence du schéma attendu. Chaque connexion active `journal_mode=WAL`,
`foreign_keys=ON`, `busy_timeout=5000`, `secure_delete=ON` et tente d'exposer
FTS5 lorsque la compilation de SQLite le permet.

### Activer le chiffrement SQLCipher

Watcher détecte automatiquement la prise en charge de
[SQLCipher](https://www.zetetic.net/sqlcipher/). Lorsque le binaire `sqlite3`
est compilé avec cette extension, vous pouvez chiffrer la base mémoire en
définissant les variables d'environnement suivantes avant de lancer
l'application :

```bash
export WATCHER_MEMORY_ENABLE_SQLCIPHER=1
export WATCHER_MEMORY_SQLCIPHER_PASSWORD="motdepasse-solide"
```

Si SQLCipher n'est pas détecté ou si le mot de passe est absent, Watcher
revient automatiquement à un stockage non chiffré et inscrit un avertissement
dans les journaux pour faciliter le diagnostic.

## Utilisation

### Interface graphique

Sous Windows :

1. `./installer.ps1 -SkipOllama` pour installer l'environnement local sans télécharger les modèles Ollama.
   Omettez l'option `-SkipOllama` pour déclencher l'installation complète lorsque vous avez besoin des modèles.
2. `./run.ps1`

Dans un environnement sans serveur d'affichage (CI, sessions distantes), forcez le mode headless en vidant `DISPLAY`
avant d'exécuter le lanceur :

```powershell
$env:DISPLAY = ""
./run.ps1
```

### Ligne de commande

```bash
python -m app.ui.main
```

### Générer une CLI Python

Un utilitaire `create_python_cli` (dans `app.tools.scaffold`) permet de
générer un squelette de projet sous `app/projects/<nom>`. Passer
`force=True` écrase les fichiers existants sans demande de confirmation.

## Plugins

Watcher peut être étendu par des plugins implémentant l'interface
`Plugin` définie dans `app/tools/plugins`. Chaque plugin expose un
attribut `name` ainsi qu'une méthode `run()` retournant un message à
l'utilisateur.

Deux mécanismes de découverte sont supportés :

- déclaration explicite dans le fichier `plugins.toml` ;
- [entry points](https://packaging.python.org/en/latest/specifications/entry-points/)
  Python via le groupe `watcher.plugins` recherchés par
  `discover_entry_point_plugins()`.

Pour enregistrer un plugin via les entry points dans un projet
emballé, ajoutez par exemple dans votre `pyproject.toml` :

```toml
[project.entry-points."watcher.plugins"]
hello = "monpaquet.monmodule:MonPlugin"
```

Un exemple minimal est fourni dans `app/tools/plugins/hello.py`.

## Tests & Qualité

Watcher s'appuie désormais sur [Nox](https://nox.thea.codes/) pour unifier les
linters, l'analyse statique, les tests et la construction du package :

```bash
nox -s lint typecheck security tests
```

Les sessions peuvent également être exécutées individuellement (`nox -s lint`,
`nox -s tests`, etc.) et une étape `nox -s build` génère les artefacts wheel et
sdist.

Pour automatiser les corrections, la cible `make format` applique Ruff (lint
et formattage) puis Black, et `make check` délègue dorénavant à Nox.

### Hooks pre-commit

Le dépôt inclut une configuration `pre-commit` regroupant les hooks suivants :

* Ruff (`ruff` et `ruff-format`) pour le linting et le formatage.
* Black pour garantir un style Python cohérent.
* mypy (avec `types-requests`) pour la vérification de types statique.
* Bandit pour l'analyse de sécurité.
* Semgrep basé sur `config/semgrep.yml`.
* Codespell pour détecter les fautes de frappe courantes.
* `end-of-file-fixer` qui s'assure que chaque fichier texte se termine par une
  nouvelle ligne.
Après avoir installé les dépendances de
développement, activez les hooks localement :

```bash
pre-commit install
```

Vous pouvez ensuite valider l'ensemble des fichiers :

```bash
pre-commit run --all-files
```

La configuration `bandit.yml` exclut notamment les répertoires `.git`, `datasets`,
`.venv`, `build`, `dist` et `*.egg-info` afin d'éviter l'analyse de contenus
non pertinents.

## Gouvernance des contributions

Les attentes pour les contributeurs et les canaux d'escalade sont décrites dans le [Code de conduite](CODE_OF_CONDUCT.md).
Pour préparer votre environnement, exécuter les scripts nécessaires (Nox, DVC, benchmarks) et comprendre la politique de
review/merge, consultez le guide [CONTRIBUTING.md](CONTRIBUTING.md).

- Les formulaires présents dans `.github/ISSUE_TEMPLATE/` ajoutent
  systématiquement `status:needs-triage` ainsi qu'un label `type:*`
  (`type:bug`, `type:feature`, `type:discussion`).
- Le fichier `.github/CODEOWNERS` assigne les revues aux équipes responsables.
  Adaptez les alias (`@WatcherOrg/...`) à votre organisation GitHub.
- Avant toute fusion, assurez-vous que `nox -s lint typecheck security tests
  build` est vert sur la CI et qu'au moins un CODEOWNER a approuvé la PR. Un
  mainteneur peut ensuite poser `status:ready-to-merge` qui déclenchera la
  fusion automatique.

Pour plus de détails (priorités, gestion du label `blocked`, etc.), consultez
`docs/merge-policy.md`.

## Reproductibilité

Un utilitaire `set_seed` permet de fixer la graine aléatoire pour Python,
NumPy et, si disponible, PyTorch. Le fichier de configuration
`config/settings.toml` contient un paramètre `seed` dans la section `[training]`
qui peut être adapté pour garantir des exécutions déterministes.

La commande CLI `watcher` lit cette graine au démarrage (ou l'option
`--seed`) puis appelle `set_seed` avant de déléguer aux sous-commandes.
Cela initialise toutes les bibliothèques stochastiques et met à jour les
variables d'environnement `PYTHONHASHSEED` et `WATCHER_TRAINING__SEED` pour que
les sous-processus héritent de la configuration.

La chaîne d'outils reproduit le même comportement :

- la CI exporte `PYTHONHASHSEED=42`, `WATCHER_TRAINING__SEED=42`,
  `CUBLAS_WORKSPACE_CONFIG=:4096:8` et `TORCH_DETERMINISTIC=1` ;
- le `Makefile` et le script PowerShell `run.ps1` propagent ces variables
  (avec une graine configurable via `SEED`/`WATCHER_TRAINING__SEED`).

Pour vos exécutions locales, vous pouvez soit utiliser le `Makefile`
(`make check`, `make nox`, …), soit exporter explicitement les variables
précitées avant de lancer vos scripts afin d'aligner l'environnement avec
la configuration versionnée.

## Données

La pipeline [DVC](https://dvc.org/) décrite dans `dvc.yaml` prépare et valide le
jeu de données linéaire utilisé par `train.py` :

- `prepare-data` lit `datasets/raw/simple_linear.csv`, applique les paramètres
  définis dans `params.yaml` (graine, taille d'échantillon) et génère
  `datasets/processed/simple_linear.csv`.
- `validate-data` utilise `foreach` pour produire trois sous-étapes
  (`validate-data@schema`, `validate-data@size`, `validate-data@hash`).
  Chacune exécute un script dédié dans `scripts/validate_*.py` pour
  vérifier respectivement le schéma, la taille et le hachage du fichier
  produit.

Les hyperparamètres d'entraînement ainsi que les contraintes de validation sont
centralisés dans `params.yaml` (syntaxe JSON valide YAML pour éviter d'ajouter
une dépendance d'analyse). Pour exécuter la pipeline complète et garantir
que les validations passent, lancez :

```bash
dvc repro validate-data
```

Un remote S3 nommé `storage` est configuré dans `.dvc/config` (URL
`s3://watcher-artifacts`). Renseignez vos identifiants AWS via les variables
d'environnement standard (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
éventuellement `AWS_SESSION_TOKEN` ou `AWS_PROFILE`) puis synchronisez les
artefacts DVC avec :

```bash
# envoyer les données préparées sur le bucket
dvc push
# récupérer les dernières versions depuis le stockage
dvc pull
```

Vous pouvez remplacer le bucket par un autre en adaptant la configuration du
remote :

```bash
dvc remote modify storage url s3://votre-bucket
```

Pour cibler un autre fournisseur, créez un remote dédié et rendez-le
par défaut. Exemple avec Azure Blob Storage :

```bash
dvc remote add -d azure azure://mon-container/datasets
dvc remote modify azure connection_string "DefaultEndpointsProtocol=..."
```

Consultez la [documentation DVC](https://dvc.org/doc/command-reference/remote)
pour les paramètres spécifiques (S3, Azure, GCS, etc.).

### Collecte

Un module de scraping asynchrone (`app/data/scraper.py`) permet de
collecter des pages web en parallèle tout en les mettant en cache sur
disque. Les téléchargements déjà effectués ne sont pas relancés, ce qui
accélère les itérations et facilite la reprise après interruption.

## Structure du dépôt

- `app/` : moteur principal, mémoire, benchmarks et interface utilisateur.
- `datasets/` : jeux d'entraînement Python (`fib`, `fizzbuzz`, `is_prime`).
- `config/` : paramètres et règles de sécurité (`semgrep`).

## Sécurité

Sandbox d'exécution confinée, tests et linters obligatoires avant adoption de code.
Semgrep utilise un fichier de règles local (`config/semgrep.yml`), aucun accès réseau requis.

Les utilitaires de sécurité tiers (`gitleaks`, `trivy`) sont téléchargés depuis leurs
releases GitHub officielles et systématiquement vérifiés via une empreinte SHA-256.
Le script `scripts/install_cli_tools.py` contrôle à la fois l'archive récupérée et
le binaire extrait (pour déjouer une compromission dans l'archive) avant de les
copier dans `.tools/`. Une divergence déclenche désormais un `InstallationError`
et interrompt l'installation des outils.

Pour le périmètre supporté, les canaux de signalement privés (PGP, formulaire, programme HackerOne) et les délais de réponse,
consultez la [politique de sécurité](SECURITY.md).
Les signalements doivent respecter la politique d'embargo décrite dans ce document et utiliser l'adresse dédiée
`security@watcher.dev` ou l'un des autres canaux indiqués.

## Confidentialité

Watcher fonctionne hors ligne par défaut et n'envoie aucune donnée vers l'extérieur.
Les journaux comme les contenus mémorisés restent sur l'environnement local et peuvent être effacés par l'utilisateur.

## Configuration des logs

Watcher peut charger une configuration de journalisation personnalisée depuis un fichier YAML **ou** JSON. Définissez la
variable d'environnement `LOGGING_CONFIG_PATH` pour indiquer le chemin du fichier :

```bash
# YAML par défaut
export LOGGING_CONFIG_PATH=./config/logging.yml

# Variante JSON équivalente
export LOGGING_CONFIG_PATH=./config/logging.json
```

Les deux fichiers décrivent un pipeline avec un formatter JSON et un filtre de contexte (`RequestIdFilter`) capable d'injecter les
identifiants de requête et de trace, ainsi qu'un filtre d'échantillonnage (`SamplingFilter`). Adaptez le paramètre `sample_rate`
pour contrôler la proportion de messages conservés :

```yaml
filters:
  sampling:
    (): app.core.logging_setup.SamplingFilter
    sample_rate: 0.1  # ne journalise qu'environ 10 % des messages
```

Les clés `request_id_field`, `trace_id_field` et `sample_rate_field` peuvent être
personnalisées dans les fichiers YAML/JSON afin d'aligner les noms de colonnes
avec vos outils d'observabilité. Le module `app.core.logging_setup` expose
également `set_trace_context(trace_id, sample_rate)` pour propager dynamiquement
ces valeurs dans les journaux structurés.

Si `LOGGING_CONFIG_PATH` est absent ou que le fichier fourni est introuvable, le fichier `config/logging.yml` inclus dans le
projet est utilisé. En dernier recours, Watcher applique la configuration basique de Python (`logging.basicConfig`) avec le
niveau `INFO`.

## Éthique et traçabilité

Les actions du système sont journalisées via le module standard `logging`. Les erreurs et décisions importantes sont ainsi consignées pour audit ou débogage.

Les contenus générés peuvent être conservés dans une base SQLite par le composant de mémoire (`app/core/memory.py`). Cette base stocke textes et métadonnées afin d'offrir un historique local des opérations.

Pour un aperçu détaillé des principes éthiques et des limites d'utilisation, consultez [ETHICS.md](ETHICS.md).

