# Medibot Mali

Application locale Medibot Mali avec le service de correspondance du modèle intégré dans `model/`.

## Lancer les services séparément

Prérequis : Python 3. Depuis la racine du projet, ouvre deux terminaux.

Terminal 1 — API modèle (`127.0.0.1:8765`) :

```bash
./start_model.sh
```

Terminal 2 — site (`http://127.0.0.1:3000`) :

```bash
./start_site.sh
```

Laisse les deux terminaux ouverts. Le site interroge l’API modèle via son relais local. `Ctrl+C` dans chaque terminal arrête le service correspondant. `./start_local.sh` reste disponible pour démarrer les deux ensemble.

Le service `model/model_api.py` utilise la bibliothèque standard Python. Les datasets de symptômes et les données Synthea sont déjà présents sous `model/data/` ; les CSV sources ne sont pas modifiés par le service.

La base SQLite locale `medibot_mali.sqlite3` est créée à la racine du projet. Elle contient les données locales de démonstration et n’est pas destinée au dépôt Git.

## Comptes de démonstration

- Administrateur : `admin@medibot.local` / `Admin123!`
- Responsable : `directeur@medibot.local` / `Demo123!`
- Généraliste : `generaliste@medibot.local` / `Demo123!`
- Spécialiste : `specialiste@medibot.local` / `Demo123!`
- Infirmière : `infirmiere@medibot.local` / `Demo123!`
- Patient : `patient@medibot.local` / `Demo123!`

Le modèle fournit des correspondances indicatives avec le dataset. Les scores ne sont ni un diagnostic ni des probabilités cliniques.
