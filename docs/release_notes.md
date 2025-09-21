# Notes de version Watcher

Cette page récapitule chaque tag SemVer publié pour Watcher. Elle complète le
[`CHANGELOG`](CHANGELOG.md) en proposant une vue synthétique des fonctionnalités et en
référençant les pages GitHub Releases correspondantes.

## Synthèse des tags

| Version | Date | Points clés | Lien GitHub Releases |
| --- | --- | --- | --- |
| *(à publier)* | — | Préparez la release initiale à partir de la section `Unreleased` du [CHANGELOG](CHANGELOG.md). | [Brouillons et releases](https://github.com/<github-username>/Watcher/releases) |

!!! info "Mettre à jour dès la première release"
    Remplacez la ligne ci-dessus par un bloc par version dès qu'un tag `vMAJOR.MINOR.PATCH`
    est poussé :

    ```markdown
    ## v1.2.3 — 2025-10-07

    - 🔒 Renforcement de la politique de signatures Sigstore.
    - 🛠️ Nouveaux connecteurs de données.
    - 📦 SBOM CycloneDX enrichi (classification des licences).

    ➤ [Consulter la release GitHub](https://github.com/<github-username>/Watcher/releases/tag/v1.2.3)
    ```

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
