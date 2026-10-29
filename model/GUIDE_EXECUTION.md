# Medibot Mali — guide d’exécution

Le projet Synthea est léger : environ 54 000 observations. Il ne nécessite ni TensorFlow, ni PyTorch, ni GPU.

## Exécution locale isolée

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements_local.txt
python 04_modele_synthea.py
streamlit run app.py
```

Pour quitter l’environnement : `deactivate`

## Google Colab

Importer le ZIP du dossier dans Colab, puis exécuter :

```python
!unzip -oq model_memoire_synthea.zip -d /content/
%cd /content/model_memoire_synthea
!pip -q install -r requirements_local.txt
!python 04_modele_synthea.py
```

Pour tester l’interface dans Colab :

```python
!pip -q install streamlit localtunnel
!streamlit run app.py --server.port 8501 &>/tmp/streamlit.log &
!npx localtunnel --port 8501
```

## Résultats produits

- `resultats_serieux/metrics_synthea.json`
- `resultats_serieux/classification_report_synthea.txt`
- `models_serieux/random_forest_synthea_multilabel.pkl`
- `medibot_consultations.sqlite3` après utilisation de l’interface

Synthea est synthétique : les scores évaluent la méthode informatique, pas une performance clinique réelle.
