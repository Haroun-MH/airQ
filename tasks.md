# AirQ — Plan de tâches pour la Partie 2

> **Objectif de la Partie 2 :** poser les fondations techniques du pipeline AirQ.
> Cette partie doit rester volontairement limitée à une source d’API, à DuckDB, à dbt,
> aux tests, au contrat de données, à Docker et à la CI. L’orchestrateur, les alertes,
> le tableau de bord et le déploiement AWS sont prévus pour plus tard.

## Légende

- [ ] À faire
- [x] Terminé et vérifié
- **Owner :** personne responsable
- **Preuve :** élément vérifiable dans le dépôt, la CI ou la documentation

---

## 0. Décisions et préparation

- [x] **Désigner un owner pour chaque brique**
  - Owner Git/équipe : Haroun-MH
  - Owner ingestion : Haroun-MH
  - Owner DuckDB/dbt : Haroun-MH
  - Owner contrat : Haroun-MH
  - Owner Docker : Haroun-MH
  - Owner CI : Haroun-MH
  - Note : la Partie 2 est livrée par un seul contributeur ; la répartition entre
    coéquipiers sera faite avant les livraisons suivantes.

- [x] **Définir le périmètre technique de la Partie 2**
  - Une seule source : API OpenAQ.
  - Cibles : une ou plusieurs villes fixées dans une variable de configuration.
  - Base locale : DuckDB.
  - Transformation : dbt avec l’adaptateur DuckDB.
  - L’API Open-Meteo, dlt, le snapshot des capteurs, le LLM et la page de santé des
    données seront développés après validation de cette partie.

- [x] **Écrire les décisions dans `README.md`**
  - [x] Justifier le choix d’OpenAQ comme source initiale.
  - [x] Documenter la fréquence de mise à jour observée d’OpenAQ (à mesurer lors du
        premier appel réel ; la cadence n’est pas encore annoncée).
  - [x] Décrire la clé de lecture (`OPENAQ_API_KEY`) et sa gestion hors Git.
  - [x] Définir la période initiale de backfill, par exemple les 7 derniers jours.
  - [x] Préciser que les lectures OpenAQ ne sont pas nécessairement régulières et que la
        fréquence observée doit être mesurée avant d’être annoncée.

- [x] **Créer une issue ou une tâche par brique**
  - Chaque brique a une section dédiée dans ce fichier, avec owner, définition de
    terminé et preuve attendue.

**Preuve :** README complété et liste des owners visible dans le dépôt.

---

## 1. Git et organisation du dépôt

- [x] **Initialiser le dépôt Git proprement**
  - [x] Ajouter tous les fichiers utiles au dépôt.
  - [x] Ajouter `.gitignore` avant le premier commit.
  - [x] Ignorer `.env`, `.env.*`, secrets, fichiers de base locaux, caches et artefacts.
  - [x] Vérifier qu’aucun secret ni fichier sensible n’est suivi par Git.

- [x] **Créer un `README.md` exploitable**
  - [x] Présenter AirQ et le problème traité.
  - [x] Indiquer les prérequis (Python, Docker, clés d’API).
  - [x] Documenter l’installation.
  - [x] Documenter la commande de démarrage avec Docker.
  - [x] Documenter les commandes d’ingestion, de transformation et de test.
  - [x] Ajouter les limites connues de la Partie 2.

- [x] **Organiser le dépôt**
  - [x] `airq/` : code d’ingestion.
  - [x] `dbt/` : configuration et modèles dbt.
  - [x] `tests/` : tests Python et/ou tests du contrat.
  - [x] `contracts/` : schémas ou définitions du contrat de données.
  - [x] `Dockerfile` et `docker-compose.yml` : images et services nécessaires.
  - [x] `.github/workflows/` : pipelines CI.
  - [x] `docs/` : architecture et décisions, si nécessaire.

- [ ] **Configurer la protection de `main`**
  - [ ] Exiger une pull request avant toute fusion.
  - [ ] Exiger au moins une revue par un coéquipier.
  - [ ] Empêcher les force-push et la suppression de `main`.
  - [ ] Faire passer les contrôles CI obligatoires avant fusion.
  - Note : la configuration GitHub doit être activée dans l’interface ou via l’API
    GitHub ; le README et `docs/contributing.md` contiennent déjà les règles attendues.

- [x] **Établir le flux de contribution**
  - [x] Documenter une branche par tâche : `feature/...` ou `fix/...`.
  - [x] Faire relire chaque PR par un membre différent de son auteur.
  - [x] Ne jamais merger une PR dont la CI est rouge.

**Preuve :** README et `docs/contributing.md` à jour, aucun secret dans Git. La
protection de branche reste à confirmer sur GitHub.

---

## 2. Ingestion idempotente de l’API OpenAQ

- [ ] **Tester réellement l’API OpenAQ**
  - [ ] Obtenir/configurer une clé API.
  - [ ] Effectuer un appel minimal avec succès.
  - [x] Conserver uniquement des exemples de réponse anonymisés ou sans secret.
  - [ ] Noter la fréquence réelle des mesures et les champs disponibles.
  - [x] Vérifier les limites de débit et le comportement en cas d’erreur.
  - Note : la clé n’est pas encore disponible dans l’environnement ; le client et les
    fixtures sont prêts pour le test réel.

- [x] **Créer un client d’ingestion**
  - [x] Lire l’URL, la clé et les paramètres depuis des variables d’environnement.
  - [x] Effectuer les requêtes HTTP avec un timeout.
  - [x] Gérer les codes HTTP et erreurs réseau de manière contrôlée.
  - [x] Ajouter un nombre limité de tentatives avec backoff.
  - [x] Ne jamais afficher la clé API dans les logs.

- [x] **Normaliser la réponse OpenAQ**
  - [x] Conserver les informations utiles : ville, localisation, capteur, paramètre,
        valeur, unité et horodatage de la mesure.
  - [x] Convertir les horodatages dans un fuseau explicite, idéalement UTC.
  - [x] Définir clairement la granularité d’une observation.
  - [x] Documenter les règles de déduplication.

- [x] **Rendre l’ingestion idempotente**
  - [x] Construire une clé métier stable pour chaque observation.
  - [x] Ne pas dupliquer les données lorsqu’une mesure est reçue plusieurs fois.
  - [x] Utiliser une transaction et un upsert sur la clé métier.
  - [x] Garantir qu’un second lancement immédiat ne modifie pas le nombre de lignes.
  - [x] Conserver la mesure la plus récente en cas de mise à jour d’une ligne.

- [x] **Écrire les tests d’ingestion**
  - [x] Tester la normalisation à partir d’une réponse OpenAQ figée.
  - [x] Tester la déduplication avec deux réponses identiques.
  - [x] Tester la conservation de la mesure la plus récente pour une même clé.
  - [x] Tester le comportement lorsqu’un champ obligatoire manque.
  - [x] Tester un échec HTTP contrôlé.

- [x] **Documenter l’idempotence**
  - [x] Ajouter une commande permettant de lancer deux fois l’ingestion.
  - [x] Expliquer comment comparer le nombre de lignes avant et après.
  - [x] Enregistrer la preuve attendue dans le README ou dans la PR.

**Preuve :** `tests/test_load.py::test_running_ingestion_twice_does_not_create_duplicates`
et le README. Le test réel avec une clé OpenAQ reste à effectuer.

---

## 3. DuckDB et dbt

- [x] **Configurer DuckDB**
  - [x] Fixer un chemin de base de données versionnable ou documenté.
  - [x] Ne pas versionner la base DuckDB si elle est générée.
  - [x] Vérifier que le chemin fonctionne sous Windows, Linux et dans Docker.
  - [x] Prévoir la création automatique de la base et du schéma.

- [x] **Initialiser dbt pour DuckDB**
  - [x] Installer/configurer l’adaptateur DuckDB.
  - [x] Renseigner le profil dbt sans secret en clair.
  - [x] Configurer les chemins de staging, intermediate et marts.
  - [x] Vérifier que `dbt debug` réussit dans l’environnement local.
  - [x] Décider où sont stockés les manifestes et logs pour la CI.

- [x] **Créer un modèle staging**
  - [x] Source : table produite par l’ingestion OpenAQ.
  - [x] Nettoyer les noms de colonnes.
  - [x] Typer correctement les mesures, unités et horodatages.
  - [x] Définir une clé unique par observation.
  - [x] Filtrer uniquement les lignes pouvant être utilisées par les modèles aval.

- [x] **Ajouter les tests dbt**
  - [x] Test `not_null` sur les colonnes critiques.
  - [x] Test `unique` sur la clé d’identification de l’observation.
  - [x] Test `accepted_values` pour les paramètres ou unités autorisés si le modèle
        le permet.
  - [x] Documenter la signification de chaque test.

- [x] **Ajouter des tests utiles au projet**
  - [x] Tester que la valeur mesurée n’est pas négative lorsque cette règle est valide.
  - [x] Tester les valeurs autorisées pour les paramètres (`pm25`, `pm10`, `o3`, etc.).
  - [x] Ne pas confondre, dans cette partie, une valeur stable avec une valeur invalide :
        la détection d’un capteur bloqué relève de l’extension OpenAQ/Open-Meteo.

- [x] **Préparer les commandes reproductibles**
  - [x] `dbt debug`
  - [x] `dbt build`
  - [x] Tester que le modèle staging se construit dans une base vierge.

**Preuve :** `dbt/models/staging/stg_openaq_measurements.yml`, la commande
`dbt build --project-dir dbt --profiles-dir dbt` et le job CI. Vérification locale
(2026-11-16) : `dbt debug` → « All checks passed! » et `dbt build` →
`PASS=23 WARN=0 ERROR=0 TOTAL=23` sur une base vierge.

---

## 4. Contrat de données

- [x] **Choisir l’approche de contrat**
  - [x] Utiliser l’outil ou la convention déjà vu en cours pour rester cohérent.
  - [x] Définir le contrat pour la source OpenAQ avant les transformations.
  - [x] Prévoir son évolution versionnée (`v1`, `v2`, etc.).

- [x] **Écrire le contrat v1**
  - [x] Nommer la source, la fréquence et le grain des données.
  - [x] Lister les colonnes attendues.
  - [x] Définir les types, la nullabilité et les contraintes.
  - [x] Définir les paramètres et unités acceptés.
  - [x] Documenter les règles de fraîcheur attendues pour l’extension future.
  - [x] Documenter les changements incompatibles et la politique de version.

- [x] **Vérifier automatiquement le contrat**
  - [x] Valider le schéma et les règles métier contre les données ingérées.
  - [x] Faire échouer la vérification si une colonne obligatoire manque.
  - [x] Faire échouer la vérification si un type ou une contrainte est invalide.
  - [x] Produire un rapport lisible avec les anomalies trouvées.
  - [x] Tester au moins un cas de non-conformité pour prouver que le contrôle échoue
        réellement.

- [x] **Intégrer le contrat à la chaîne de validation**
  - [x] Le contrat doit être exécutable par une commande unique.
  - [x] Le résultat doit être exploitable par la CI.
  - [x] La documentation doit expliquer comment lancer la vérification localement.

**Preuve :** `contracts/openaq.yaml`, la commande `datacontract test`, le job CI et le
test d’invalidation `tests/test_contract.py`.

---

## 5. Docker et orchestration locale minimale

- [x] **Créer le `Dockerfile` de l’ingestion**
  - [x] Image Python reproductible et de taille raisonnable.
  - [x] Installation des dépendances depuis les métadonnées du projet.
  - [x] Copie de l’ingestion et de la configuration nécessaire.
  - [x] Commande par défaut ou point d’entrée explicite.
  - [x] Utilisateur non-root si simple à mettre en place.

- [x] **Créer le `docker-compose.yml`**
  - [x] Service `ingestion`.
  - [x] Service `dbt` qui exécute `dbt build` puis le contrat.
  - [x] Volume ou stockage persistant pour DuckDB.
  - [x] Variables d’environnement documentées.
  - [x] Dépendance `service_completed_successfully` entre ingestion et dbt.
  - [x] Statut de sortie vérifiable pour chaque service.

- [ ] **Tester le démarrage complet**
  - [ ] Vérifier `docker compose build`.
  - [ ] Vérifier `docker compose up` depuis un environnement propre.
  - [ ] Vérifier que la base DuckDB et les tables dbt sont créées.
  - [ ] Vérifier que le conteneur échoue avec un code non nul si la CI échoue.
  - [ ] Vérifier qu’une seconde exécution ne crée pas de doublons.
  - Note : Docker Desktop est installé, mais son daemon n’était pas démarré pendant
    l’implémentation.

- [x] **Finaliser la commande de démarrage**
  - [x] Documenter une commande simple :
        `docker compose up --build --abort-on-container-exit`
  - [x] Éviter qu’un utilisateur doive lancer plusieurs commandes manuelles pour obtenir
        ingestion + transformations + validation.

**Preuve :** `Dockerfile`, `docker-compose.yml` et README. Le test d’exécution reste à
faire lorsque Docker Desktop est démarré.

---

## 6. GitHub Actions et merge bloqué

- [x] **Créer le workflow de pull request**
  - [x] Déclenchement sur `pull_request` vers `main`.
  - [x] Permissions minimales (`contents: read`).
  - [x] Installation de Python avec une version épinglée.
  - [x] Installation des dépendances depuis les métadonnées du projet.
  - [x] Installation de DuckDB et dbt DuckDB.

- [x] **Exécuter les tests Python**
  - [x] Lancer la suite de tests de l’ingestion.
  - [x] Le workflow échoue si un test échoue.

- [x] **Exécuter la vérification du contrat**
  - [x] Lancer la commande de vérification du contrat.
  - [x] Le workflow échoue si le contrat n’est pas respecté.

- [x] **Exécuter dbt**
  - [x] Lancer `dbt build` sur une base DuckDB vierge.
  - [x] Le workflow échoue si une transformation ou un test dbt échoue.
  - [x] Conserver les logs utiles en artefacts de CI.

- [ ] **Tester la CI avec une PR volontairement rouge**
  - [ ] Ajouter un test ou une violation temporaire.
  - [ ] Vérifier que la PR passe en rouge.
  - [ ] Vérifier que la fusion est impossible tant que le contrôle échoue.
  - [ ] Supprimer la modification après la preuve.

- [x] **Configurer les secrets**
  - [x] Prévoir l’ajout de `OPENAQ_API_KEY` dans les secrets GitHub si la CI en a besoin.
  - [x] Ne jamais afficher le secret dans les logs.
  - [x] Vérifier qu’aucun secret GitHub n’apparaît dans le dépôt.

- [ ] **Finaliser la protection de `main`**
  - [ ] `main` exige une PR.
  - [ ] `main` exige au moins une revue.
  - [ ] `main` exige le statut CI `validate` réussi.
  - Note : à activer dans les paramètres GitHub du dépôt.

**Preuve :** `.github/workflows/ci.yml`. La preuve verte/rouge sur GitHub reste à
produire après la première PR.

---

## 7. Vérification finale de la Partie 2

- [ ] **Partie Git**
  - [ ] README clair et à jour.
  - [ ] `main` protégé.
  - [ ] Aucune fusion directe sur `main`.
  - [ ] `.env` et les secrets ignorés.

- [ ] **Partie ingestion**
  - [ ] Une source API réellement testée.
  - [ ] Ingestion exécutable.
  - [ ] Deux exécutions successives donnent le même nombre de lignes.

- [ ] **Partie DuckDB/dbt**
  - [ ] Base DuckDB générable depuis zéro.
  - [ ] Au moins un modèle staging.
  - [ ] Tests `not_null` et `unique` présents et passants.

- [ ] **Partie contrat**
  - [ ] Contrat versionné.
  - [ ] Vérification automatique.
  - [ ] La vérification échoue sur une donnée non conforme.

- [ ] **Partie Docker**
  - [ ] `docker compose up` lance ingestion + dbt.
  - [ ] Le README contient les commandes exactes.

- [ ] **Partie CI**
  - [ ] GitHub Actions se déclenche à chaque PR.
  - [ ] Tests, contrat et dbt sont exécutés.
  - [ ] Une PR rouge est bloquée.

- [ ] **Règles d’équipe**
  - [ ] Chaque coéquipier a travaillé sur au moins deux briques.
  - [ ] L’historique Git montre qui a fait quoi.
  - [ ] Chaque coéquipier peut expliquer chaque ligne du dépôt.
  - [ ] Les contributions IA sont autorisées, mais comprises et vérifiées par l’équipe.

---

## Ordre d’exécution recommandé

1. Git, `.gitignore` et structure du dépôt.
2. Test de l’API OpenAQ et définition du grain des données.
3. Ingestion idempotente et tests Python.
4. DuckDB, dbt, modèle staging et tests dbt.
5. Contrat v1 et vérification automatique.
6. Docker Compose.
7. GitHub Actions.
8. PRs de démonstration : ingestion idempotente, violation de contrat et PR rouge.
9. Revue d’équipe, correction de la documentation et validation finale.

## Hors périmètre de la Partie 2

À planifier dans une livraison ultérieure, sans bloquer la validation des fondations :

- Ingestion Open-Meteo.
- dlt incrémental et snapshots de dbt.
- Détection d’un capteur bloqué sur plusieurs intervalles.
- Prefect ou Airflow.
- Tableau de bord et page publique « santé des données ».
- Résumé quotidien généré par un LLM.
- Alertes, observabilité avancée et déploiement AWS.

## Critères de réussite

La Partie 2 est validée lorsqu’un nouveau clone du dépôt peut :

1. Configurer les prérequis et le secret API.
2. Lancer Docker Compose.
3. Ingérer les données OpenAQ.
4. Construire les modèles dbt et leurs tests.
5. Valider le contrat.
6. Obtenir une CI verte sur la pull request.

La démonstration de l’idempotence — **même nombre de lignes après deux exécutions** — doit
être comprise dans cette procédure et visible dans la PR de validation.
