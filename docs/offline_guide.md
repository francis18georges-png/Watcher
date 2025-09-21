# Exploitation en environnement air-gap

Ce guide décrit la préparation et l'exploitation de Watcher dans un réseau isolé (air-gap).
L'objectif est de transférer un kit complet — exécutables, dépendances Python, SBOM et
attestations — depuis une zone connectée vers une enclave déconnectée, tout en conservant les
contrôles d'intégrité.

## 1. Préparer le kit hors-ligne sur une machine connectée

1. **Téléchargez les artefacts de release** depuis GitHub pour le tag ciblé (par exemple [v0.4.0](https://github.com/<owner>/Watcher/releases/tag/v0.4.0)) :

   ```bash
   mkdir -p ~/watcher-offline-kit/artifacts
   cd ~/watcher-offline-kit/artifacts
   gh release download <tag> --repo <owner>/Watcher
   ```

   Ce répertoire doit contenir au minimum :

   - `Watcher-Setup.zip`, `Watcher-linux-x86_64.tar.gz`, `Watcher-macos-x86_64.zip`.
   - Les SBOM (`Watcher-*.json`).
   - L'attestation SLSA (`Watcher-Setup.intoto.jsonl`).
   - Les bundles Sigstore (`*.sigstore`) et les `sha256sum`.

   Le CLI `gh` facilite le téléchargement groupé ; à défaut, récupérez les mêmes fichiers via
   l'interface web ou `curl -L -O`.

2. **Constituez un miroir PyPI minimal** contenant les dépendances Python nécessaires :

   ```bash
   cd ~/watcher-offline-kit
   python -m venv venv
   source venv/bin/activate
   pip install --upgrade pip wheel
   pip download -r /workspace/Watcher/requirements.txt --dest ./pypi-mirror
   pip download -r /workspace/Watcher/requirements-dev.txt --dest ./pypi-mirror
   deactivate
   ```

   Le dossier `pypi-mirror/` pourra être copié tel quel dans l'enclave et utilisé avec
   `pip install --no-index --find-links ./pypi-mirror`.

3. **Sauvegardez la configuration et les prompts** qui accompagnent le binaire :

   ```bash
   rsync -av --progress /workspace/Watcher/config ~/watcher-offline-kit/
   rsync -av --progress /workspace/Watcher/example.env ~/watcher-offline-kit/
   rsync -av --progress /workspace/Watcher/requirements*.txt ~/watcher-offline-kit/
   ```

4. **Archivez le tout** pour faciliter le transfert physique (clé USB, disque chiffré) :

   ```bash
   tar -czf watcher-offline-kit.tgz -C ~/watcher-offline-kit .
   ```

## 2. Vérifier les artefacts sans connexion

Dans l'environnement air-gap, recopiez l'archive et exécutez les contrôles suivants avant toute
installation :

```bash
mkdir -p ~/watcher
cd ~/watcher
tar -xzf /mnt/usb/watcher-offline-kit.tgz
```

1. **Empreintes SHA256** :

   ```bash
   sha256sum --check sha256sums.txt
   ```

2. **Signatures Sigstore** (fonctionnent hors-ligne grâce aux bundles) :

   ```bash
   sigstore verify identity \
     --bundle artifacts/Watcher-Setup.zip.sigstore \
     --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/<tag>" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     artifacts/Watcher-Setup.zip
   ```

3. **Attestation SLSA** :

   ```bash
   cosign verify-attestation \
     --type slsaprovenance \
     --bundle artifacts/Watcher-Setup.intoto.jsonl.sigstore \
     --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/<tag>" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     artifacts/Watcher-Setup.intoto.jsonl | jq '.subject'
   ```

4. **SBOM CycloneDX** :

   ```bash
   cosign verify-attestation \
     --type cyclonedx \
     --bundle artifacts/Watcher-sbom.json.sigstore \
     --certificate-identity "https://github.com/<owner>/Watcher/.github/workflows/release.yml@refs/tags/<tag>" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     artifacts/Watcher-sbom.json | jq '.predicate.metadata'
   ```

Conservez les journaux de ces commandes comme preuves d'intégrité et stockez-les avec les
artefacts validés.

## 3. Installer Watcher sans accès Internet

1. **Installer les dépendances Python** depuis le miroir local :

   ```bash
   python3 -m venv watcher-venv
   source watcher-venv/bin/activate
   pip install --no-index --find-links ./pypi-mirror -r requirements.txt
   ```

2. **Déployer le binaire** correspondant à votre plateforme :

   - Windows : décompressez `Watcher-Setup.zip` et copiez le dossier sur la machine cible.
   - Linux : `tar -xzf Watcher-linux-x86_64.tar.gz -C /opt/watcher` puis `ln -sf /opt/watcher/Watcher /usr/local/bin/watcher`.
   - macOS : `unzip Watcher-macos-x86_64.zip` et placez l'application dans `/Applications`.

3. **Configurer l'environnement** :

   - Dupliquez `example.env` en `.env` et renseignez les clés API locales.
   - Mettez à jour les chemins de stockage dans `config/settings.yaml` pour pointer vers des
     répertoires internes à l'enclave.
   - Activez, si nécessaire, le mode `offline` dans la configuration afin de désactiver les
     intégrations nécessitant Internet.

## 4. Mettre à jour le kit hors-ligne

- Planifiez un cycle de rafraîchissement (par exemple mensuel). Lorsqu'un nouveau tag est publié,
  recréez le `watcher-offline-kit.tgz` avec les dernières dépendances, SBOM et attestations.
- Utilisez `diff -ru` entre deux kits pour identifier rapidement les fichiers modifiés.
- Conservez l'historique des kits sur un support chiffré et versionné pour pouvoir revenir à
  une version antérieure en cas d'incident.

## 5. Bonnes pratiques de sécurité

- Transportez les supports physiques dans des sacs scellés et consignez chaque transfert.
- Vérifiez la date de validité des certificats Sigstore : une alerte de révocation doit déclencher
  un nouveau téléchargement dans la zone connectée.
- Limitez l'accès au miroir PyPI local aux seules machines de confiance et nettoyez-le après
  chaque mise à jour.

En suivant ces étapes, Watcher peut être installé et maintenu dans une enclave totalement
isolée tout en respectant les exigences de traçabilité et d'intégrité logicielle.
