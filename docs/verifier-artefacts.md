# Vérification des artefacts Watcher

Ce guide décrit la procédure **CLI réelle** pour vérifier les artefacts de release Watcher
(checksums, signature cosign et provenance SLSA), sans dépendre d'une interface graphique.

## Prérequis

- `cosign` installé (version récente).
- `sha256sum` (ou équivalent macOS `shasum -a 256`).
- Les artefacts téléchargés depuis la release GitHub (`checksums.txt`, `checksums.txt.sig`,
  `checksums.txt.pem`, paquets/binaries).

## 1) Vérifier l'intégrité locale des fichiers

Depuis le dossier de téléchargement de la release:

```bash
sha256sum -c checksums.txt
```

Attendu: toutes les lignes doivent remonter `OK`.

> macOS :
>
> ```bash
> shasum -a 256 -c checksums.txt
> ```

## 2) Vérifier la signature cosign des checksums

```bash
cosign verify-blob \
  --certificate checksums.txt.pem \
  --signature checksums.txt.sig \
  checksums.txt
```

Cette étape valide que le fichier de checksums a bien été signé.

## 3) Vérifier la provenance (attestation)

Pour les artefacts de container (si vous utilisez l'image GHCR):

```bash
cosign verify-attestation \
  --type slsaprovenance \
  ghcr.io/<owner>/watcher:<tag>
```

Pour inspecter une image multi-arch avant vérification:

```bash
docker buildx imagetools inspect ghcr.io/<owner>/watcher:<tag>
```

## 4) Vérifier la cohérence release ↔ SBOM

- Ouvrir le SBOM (`*.cdx.json`) publié dans la release.
- Vérifier que les composants majeurs attendus sont présents (runtime Python,
  dépendances critiques, versions alignées avec le tag).

## 5) Que faire en cas d'échec

- **Checksum invalide**: supprimer le fichier concerné et retélécharger depuis la release officielle.
- **Signature cosign invalide**: bloquer l'utilisation de l'artefact et ouvrir un incident sécurité.
- **Attestation absente/invalide**: considérer la release comme non conforme tant que l'équipe
  de maintenance n'a pas corrigé la publication.

## Intégration dans le parcours utilisateur

- Le [Quickstart CLI](quickstart-cli.md) renvoie vers cette page après l'installation et l'initialisation.
- Le [guide hors-ligne](offline_guide.md) complète ces contrôles pour les environnements déconnectés.
