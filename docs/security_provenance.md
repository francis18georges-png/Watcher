# Vérification de la provenance et des artefacts

La chaîne de compilation de Watcher repose sur les workflows GitHub Actions et les services
Sigstore. Chaque release SemVer publie des exécutables, un SBOM CycloneDX par plateforme et
une provenance SLSA (`*.intoto.jsonl`). Cette page décrit comment vérifier ces artefacts avant
de les déployer en production.

## Pré-requis

Installez les utilitaires suivants sur une machine de validation connectée à Internet :

- [sigstore](https://www.sigstore.dev/) pour vérifier les bundles de signatures (`*.sigstore`).
- [cosign](https://docs.sigstore.dev/cosign/overview/) pour valider les attestations SLSA et
  SBOM.
- [`jq`](https://stedolan.github.io/jq/) ou un autre parseur JSON pour inspecter les métadonnées
  retournées par `cosign`.

```bash
pipx install sigstore
brew install cosign jq  # macOS
sudo apt install cosign jq -y  # Debian/Ubuntu
```

Téléchargez ensuite, depuis la page GitHub Releases du tag visé, l'exécutable, le SBOM, la
provenance SLSA et leurs bundles Sigstore associés. Exemple pour Windows :

```text
Watcher-Setup.zip
Watcher-Setup.zip.sigstore
Watcher-Setup.intoto.jsonl
Watcher-Setup.intoto.jsonl.sigstore
Watcher-sbom.json
Watcher-sbom.json.sigstore
```

!!! tip "Utiliser les SHA256 publiés"
    Chaque release expose également les empreintes `sha256sum` en tant qu'artefacts.
    Téléchargez-les pour automatiser l'intégrité des fichiers transférés vers un réseau déconnecté.

## Vérifier la signature Sigstore (`sigstore verify`)

1. Calculez le hash du binaire pour vérifier qu'il correspond à l'empreinte publiée :

   ```bash
   sha256sum Watcher-Setup.zip
   ```

2. Vérifiez la signature du bundle Sigstore et la provenance GitHub Actions :

   ```bash
   sigstore verify identity \
     --bundle Watcher-Setup.zip.sigstore \
     --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/<tag>" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     Watcher-Setup.zip
   ```

   - Remplacez `<owner>` par l'organisation ou l'utilisateur GitHub hébergeant Watcher.
   - Substituez `<tag>` par la version téléchargée (`vMAJOR.MINOR.PATCH`).
   - La commande échoue si le bundle ne provient pas du workflow officiel `release.yml`.

3. Répétez la vérification pour les archives Linux et macOS (`Watcher-linux-x86_64.tar.gz`,
   `Watcher-macos-x86_64.zip`) en adaptant le nom du fichier et du bundle.

!!! success "Automatiser la validation"
    Intégrez ces commandes dans un script CI interne pour refuser tout artefact dont la
    signature Sigstore est absente ou invalide.

## Vérifier l'attestation SLSA (`cosign verify-attestation`)

1. Exécutez la vérification cryptographique du fichier de provenance :

   ```bash
   cosign verify-attestation \
     --type slsaprovenance \
     --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/<tag>" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     --bundle Watcher-Setup.intoto.jsonl.sigstore \
     Watcher-Setup.intoto.jsonl | jq '.'
   ```

2. Contrôlez la section `subject` du JSON retourné : le digest SHA256 doit correspondre au
   binaire validé précédemment (`Watcher-Setup.zip`).
3. Inspectez également les champs `builder.id` et `invocation.environment.githubWorkflowRef`
   pour confirmer que le workflow `release.yml` a produit l'artefact.

Pour une vérification approfondie, vous pouvez croiser cette attestation avec
[`slsa-verifier`](https://github.com/slsa-framework/slsa-verifier) et exporter un rapport PDF
pour vos audits internes.

## Vérifier le SBOM CycloneDX

Les SBOM sont publiés sous forme de fichiers JSON signés avec Sigstore. Deux étapes sont
recommandées :

1. Vérifiez la signature du SBOM à l'aide de son bundle Sigstore :

   ```bash
   sigstore verify identity \
     --bundle Watcher-sbom.json.sigstore \
     --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/<tag>" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     Watcher-sbom.json
   ```

2. Validez le lien entre le SBOM et l'artefact grâce à `cosign verify-attestation` avec le type
   `cyclonedx` :

   ```bash
   cosign verify-attestation \
     --type cyclonedx \
     --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/<tag>" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     --bundle Watcher-sbom.json.sigstore \
     Watcher-sbom.json | jq '.predicate' | less
   ```

   Le champ `predicate.metadata.component.externalRefs` doit pointer vers l'artefact (binaire,
   image ou archive) auquel le SBOM se rapporte.

3. Analysez enfin le contenu du SBOM :

   ```bash
   jq '.components[] | {name, version, licenses}' Watcher-sbom.json
   ```

   Utilisez `grype Watcher-sbom.json` ou un autre scanner pour générer un rapport de
   vulnérabilités basé sur la nomenclature CycloneDX.

## Intégrer les contrôles dans votre pipeline

- Stockez les bundles Sigstore et les attestions SLSA aux côtés des exécutables dans vos
  coffres-forts d'artefacts.
- Ajoutez un job de validation qui rejoue les commandes ci-dessus avant chaque mise en
  production.
- Archivez les journaux `sigstore`/`cosign` signés pour constituer un dossier de conformité
  (ISO 27001, SecNumCloud, etc.).

En combinant la vérification Sigstore, les attestations SLSA et l'analyse du SBOM CycloneDX,
vous obtenez une traçabilité complète de la chaîne de build Watcher.
