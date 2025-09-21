# Politique de sécurité de Watcher

## Périmètre supporté

Nous fournissons un support sécurité actif sur les versions suivantes :

- La branche `main`.
- Les versions stables SemVer publiées au cours des douze derniers mois.
- Les installeurs Windows générés par le workflow `release.yml` (binaire signé et artefacts associés).

Les forks, versions communautaires modifiées ou binaires reconstruits par des tiers ne sont pas couverts par cette politique.

## Signaler une vulnérabilité

Merci de privilégier des canaux privés pour tout signalement de vulnérabilité afin de limiter le risque d'exploitation avant qu'un correctif ne soit disponible. Utilisez en priorité le bouton **Report a vulnerability** de l'onglet *Security* du dépôt GitHub, qui ouvre le formulaire de signalement privé intégré.

Si ce canal n'est pas accessible, vous pouvez utiliser l'un des moyens suivants :

- 📧 **Email chiffré PGP** : security@watcher.dev — clé publique : https://watcher.dev/security/pgp.asc (empreinte `8A20 5D9E 3A1B F236 B179  5AA0 E2F0 3F1B 9D0F 4A17`).
- 🛡️ **Formulaire privé** : https://watcher.dev/security/report.
- 🐞 **HackerOne** : https://hackerone.com/watcher (programme privé, invitez `Watcher Security Team`).

Si vous devez partager de gros fichiers ou des captures d'écran, indiquez-le et nous vous fournirons un espace de dépôt sécurisé.

## Délais de réponse

Nous nous engageons sur les délais indicatifs suivants :

- accusé de réception sous deux jours ouvrés ;
- premier retour technique (impact, pistes de mitigation) sous cinq jours ouvrés ;
- mise à disposition d'un correctif ou d'une mitigation pour les vulnérabilités critiques sous 14 jours ouvrés, et sous 30 jours ouvrés pour les niveaux faible à élevé.

Si ces délais ne peuvent être respectés (complexité, dépendance externe), nous vous informerons de l'échéance révisée et des actions de contournement proposées.

## Politique d'embargo

Les signalements restent confidentiels jusqu'à la publication d'un correctif et l'écoulement d'un délai minimum de 7 jours ouvrés après la sortie publique afin de laisser aux utilisateurs le temps d'appliquer la mise à jour. Nous pouvons lever l'embargo plus tôt d'un commun accord si :

- une exploitation active est détectée, nécessitant une communication immédiate ;
- une autre partie rend la vulnérabilité publique avant la fin de l'embargo.

En dehors de ces cas, merci de ne pas divulguer d'informations techniques (PoC, détails exploitables) avant la fin de la fenêtre d'embargo.

## Hors périmètre

Les sujets suivants ne sont pas éligibles à des SLA ni à des récompenses éventuelles :

- problèmes liés à des dépendances tierces sans scénario d'exploitation dans Watcher ;
- vulnérabilités sur des versions abandonnées ou des forks communautaires ;
- divulgation d'informations déjà publiques ou provenant de sources tierces compromises.

Nous restons disponibles pour répondre à vos questions à l'adresse security@watcher.dev.
