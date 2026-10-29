#!/usr/bin/env python3
"""Experimentation séparée basée sur les dossiers Synthea."""
from pathlib import Path
import json, warnings
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score, hamming_loss, classification_report
from sklearn.model_selection import train_test_split
from sklearn.multioutput import MultiOutputClassifier
from sklearn.preprocessing import MultiLabelBinarizer
import joblib
warnings.filterwarnings("ignore")
BASE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
DATA = BASE / "data" / "synthea"
OUT, MODELS = BASE / "resultats_serieux", BASE / "models_serieux"
OUT.mkdir(exist_ok=True); MODELS.mkdir(exist_ok=True)
SEED = 42

def build_patient_table():
    patients = pd.read_csv(DATA / "patients.csv", usecols=["Id", "BIRTHDATE", "GENDER", "RACE"])
    patients["age"] = 2026 - pd.to_datetime(patients["BIRTHDATE"]).dt.year
    patients = pd.get_dummies(patients.drop(columns=["BIRTHDATE"]), columns=["GENDER", "RACE"], dtype=float)
    obs = pd.read_csv(DATA / "observations.csv", usecols=["PATIENT", "DESCRIPTION", "VALUE"])
    obs["numeric"] = pd.to_numeric(obs["VALUE"].astype(str).str.replace(",", "."), errors="coerce")
    numeric = obs.dropna(subset=["numeric"]).pivot_table(index="PATIENT", columns="DESCRIPTION", values="numeric", aggfunc="mean")
    numeric.columns = ["obs_" + str(c)[:70] for c in numeric.columns]
    X = patients.set_index("Id").join(numeric, how="left").fillna(0)
    cond = pd.read_csv(DATA / "conditions.csv", usecols=["PATIENT", "DESCRIPTION"])
    targets = cond.DESCRIPTION.value_counts().loc[lambda s: s >= 10].head(10).index.tolist()
    labels = cond[cond.DESCRIPTION.isin(targets)].groupby("PATIENT").DESCRIPTION.apply(set)
    mlb = MultiLabelBinarizer(classes=targets)
    Y = pd.DataFrame(mlb.fit_transform(X.index.map(lambda p: labels.get(p, set()))), index=X.index, columns=targets)
    keep = Y.sum(axis=1) > 0
    return X.loc[keep], Y.loc[keep], targets, len(obs), len(cond)

def main():
    X, Y, targets, n_obs, n_cond = build_patient_table()
    Xtr, Xte, Ytr, Yte = train_test_split(X, Y, test_size=.25, random_state=SEED)
    base = RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=2, class_weight="balanced", n_jobs=-1, random_state=SEED)
    model = MultiOutputClassifier(base, n_jobs=-1).fit(Xtr, Ytr)
    pred = model.predict(Xte)
    metrics = {"patients_used": int(len(X)), "observations_source_rows": int(n_obs), "conditions_source_rows": int(n_cond), "features": int(X.shape[1]), "targets": targets, "test_patients": int(len(Xte)), "f1_macro": float(f1_score(Yte, pred, average="macro", zero_division=0)), "hamming_loss": float(hamming_loss(Yte, pred)), "note": "Synthea est synthétique; ce score ne constitue pas une validation clinique."}
    (OUT / "metrics_synthea.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "classification_report_synthea.txt").write_text(classification_report(Yte, pred, target_names=targets, zero_division=0), encoding="utf-8")
    joblib.dump(model, MODELS / "random_forest_synthea_multilabel.pkl")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
if __name__ == "__main__": main()
