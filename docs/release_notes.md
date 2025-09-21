# Notes de version Watcher

Cette page récapitule chaque tag SemVer publié pour Watcher. Elle complète le
[`CHANGELOG`](CHANGELOG.md) en proposant une vue synthétique des fonctionnalités et en
référençant les pages GitHub Releases correspondantes.

## Synthèse des tags

| Version | Date | Points clés | Lien GitHub Releases |
| --- | --- | --- | --- |
| v0.4.0 | 20 septembre 2025 | - Configurer les versions Python ciblées par Nox et CI.<br>- Ajouter des property tests compatibles numpy-stub.<br>- Améliorer les workflows de release et de conteneurisation. | [Consulter la release v0.4.0](https://github.com/<owner>/Watcher/releases/tag/v0.4.0) |

!!! info "Suivre les prochaines versions"
    Ajoutez une nouvelle ligne à ce tableau et un bloc dédié dès qu'un tag `vMAJOR.MINOR.PATCH`
    est poussé.

## v0.4.0 — 2025-09-20

- 🛠️ Configuration explicite des versions Python ciblées par Nox et par la CI.
- ✅ Ajout de property tests compatibles avec les stubs numpy.
- 🚀 Optimisations des workflows de release et de build de conteneurs.
- 📚 Documentation du blocage réseau dans la configuration par défaut.

➤ [Consulter la release GitHub](https://github.com/<owner>/Watcher/releases/tag/v0.4.0)

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
