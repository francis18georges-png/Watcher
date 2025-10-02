# Notes de version Watcher

Cette page récapitule chaque tag SemVer publié pour Watcher. Elle complète le
[`CHANGELOG`](CHANGELOG.md) en proposant une vue synthétique des fonctionnalités et en
référençant les pages GitHub Releases correspondantes.

## Synthèse des tags

| Version | Date | Points clés | Lien GitHub Releases |
| --- | --- | --- | --- |
| v0.4.0 | À venir | - Configurer les versions Python ciblées par Nox et CI.<br>- Ajouter des property tests compatibles numpy-stub.<br>- Améliorer les workflows de release et de conteneurisation. | À venir |

!!! info "Suivre les prochaines versions"
    Ajoutez une nouvelle ligne à ce tableau et un bloc dédié dès qu'un tag `vMAJOR.MINOR.PATCH`
    est poussé.

## v0.4.0 — en préparation

!!! warning "Release GitHub en préparation"
    La publication officielle de la version `v0.4.0` n'est pas encore disponible sur GitHub.
    Les liens directs et la date finale seront ajoutés dès que le tag sera créé.

- 🛠️ Configuration explicite des versions Python ciblées par Nox et par la CI.
- ✅ Ajout de property tests compatibles avec les stubs numpy.
- 🚀 Optimisations des workflows de release et de build de conteneurs.
- 📚 Documentation du blocage réseau dans la configuration par défaut.

➤ Lien GitHub : à venir

### Vérifier les artefacts de la release v0.4.0

Ces vérifications seront possibles une fois que la publication GitHub sera en ligne. Les
commandes ci-dessous sont conservées à titre de checklist.

1. Téléchargez les binaires et métadonnées depuis la release officielle :

   ```bash
   RELEASE="https://github.com/francis18georges-png/Watcher/releases/download/v0.4.0"
   wget "$RELEASE/Watcher-Setup.zip" \
        "$RELEASE/Watcher-Setup.zip.sigstore" \
        "$RELEASE/Watcher-Setup.intoto.jsonl" \
        "$RELEASE/Watcher-sbom.json" \
        "$RELEASE/Watcher-linux-x86_64.tar.gz" \
        "$RELEASE/Watcher-linux-sbom.json" \
        "$RELEASE/Watcher-macos-x86_64.zip" \
        "$RELEASE/Watcher-macos-sbom.json"
   ```

2. Vérifiez la signature Sigstore du binaire Windows :

   ```bash
   sigstore verify identity \
     --bundle Watcher-Setup.zip.sigstore \
     --certificate-identity "https://github.com/francis18georges-png/Watcher/.github/workflows/release.yml@refs/tags/v0.4.0" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     Watcher-Setup.zip
   ```

3. Vérifiez l'attestation de provenance SLSA :

   ```bash
   slsa-verifier verify-artifact \
     --provenance Watcher-Setup.intoto.jsonl \
     --source-uri github.com/francis18georges-png/Watcher \
     --source-tag v0.4.0 \
     Watcher-Setup.zip
   ```

4. Contrôlez les empreintes `sha256sum` des binaires et comparez-les à celles publiées dans la release :

   ```bash
   sha256sum Watcher-Setup.zip \
             Watcher-linux-x86_64.tar.gz \
             Watcher-macos-x86_64.zip
   ```

5. Explorez les SBOM pour auditer les dépendances :

   ```bash
   cyclonedx-py validate Watcher-sbom.json
   jq '.components[] | {name, version}' Watcher-linux-sbom.json | head
   ```

6. Archivez le rapport `pip-audit-report.json` et les distributions Python pour des installations offline.

## Processus de publication

1. Créez un tag annoté sur la branche `main` :

   ```bash
   git tag -a vMAJOR.MINOR.PATCH -m "Watcher vMAJOR.MINOR.PATCH"
   git push origin vMAJOR.MINOR.PATCH
   ```

2. Vérifiez sur GitHub que le workflow `release.yml` a bien généré :

   - Les exécutables (`Watcher-Setup.zip`, `Watcher-linux-x86_64.tar.gz`, `Watcher-macos-x86_64.zip`).
   - Les SBOM CycloneDX (`Watcher-*-sbom.json`).
   - L'attestation SLSA (`Watcher-Setup.intoto.jsonl`).
   - Les bundles Sigstore (`*.sigstore`).

3. Complétez la description de la release avec :

   - Un résumé des nouveautés (copié/collé de cette page et du CHANGELOG).
   - Les instructions de vérification (`sigstore verify`, `cosign verify-attestation`).
   - Les empreintes `sha256sum` pour chaque artefact.

## Historiser les mises à jour

- Ajoutez un bloc `## vX.Y.Z — YYYY-MM-DD` pour chaque tag publié, avec les points clés et les
  liens pertinents (issues, PR, tickets internes).
- Conservez une tonalité orientée produit : décrivez l'impact utilisateur, pas uniquement
  les changements techniques.
- Archivez un PDF de la release (fonction *Export release notes*) pour les besoins de conformité.

Cette page sert de table d'orientation rapide pour savoir quelles fonctionnalités sont
contenues dans chaque version officielle de Watcher.
