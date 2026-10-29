"""Service d'orientation par correspondance avec le jeu de symptômes fourni.

Ce service est séparé de l'application hôpital. Il ne prétend pas être un
classifieur clinique validé : il compare la combinaison reçue aux exemples de
Training.csv et renvoie les maladies et précautions présentes dans les CSV.
"""
from pathlib import Path
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data'
TRAINING = DATA / 'Training.csv'
PRECAUTIONS = DATA / 'symptom_precaution.csv'
DESCRIPTIONS = DATA / 'symptom_Description.csv'
DISCLAIMER = ('Correspondances indicatives avec le dataset uniquement. '
              'Ce résultat n’est ni un diagnostic ni une probabilité clinique.')


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def load_rows():
    return read_csv(TRAINING)


def catalog():
    with TRAINING.open(encoding='utf-8-sig', newline='') as handle:
        # Le CSV fourni répète le nom loss_of_smell dans son en-tête.
        # Dédupliquer le catalogue UI sans modifier les données sources.
        return list(dict.fromkeys(name for name in next(csv.reader(handle))[:-1] if name))


def symptom_profiles():
    rows = load_rows()
    keys = [k for k in rows[0] if k != 'prognosis'] if rows else []
    profiles = []
    for row_no, row in enumerate(rows, start=2):
        active = {key for key in keys if row.get(key) == '1'}
        if active:
            profiles.append((row_no, row.get('prognosis', '').strip(), active))
    return keys, profiles


def catalog_with_counts():
    keys, profiles = symptom_profiles()
    return {'symptoms': keys, 'popular': sorted(keys, key=lambda key: (-sum(key in p[2] for p in profiles), key))[:20]}


def predict(payload):
    selected = set(payload.get('symptoms') or [])
    keys, profiles = symptom_profiles()
    unknown = sorted(selected - set(keys))
    selected &= set(keys)
    if not selected:
        return {'predictions': [], 'unknown_symptoms': unknown, 'disclaimer': DISCLAIMER,
                'matching_method': 'nearest symptom profiles in Training.csv'}

    # Les CSV contiennent des répétitions de profils. Dédupliquer ces profils
    # évite de compter plusieurs fois le même exemple synthétique. On classe
    # chaque maladie par la similarité moyenne de ses cinq profils distincts
    # les plus proches. Aucun a priori géographique ou saisonnier n'est injecté.
    profiles_by_disease = {}
    for row_no, disease, active in profiles:
        signature = tuple(sorted(active))
        profiles_by_disease.setdefault(disease, {}).setdefault(signature, row_no)

    by_disease = {}
    for disease, signatures in profiles_by_disease.items():
        examples = []
        for signature, row_no in signatures.items():
            active = set(signature)
            overlap = selected & active
            if not overlap:
                continue
            similarity = len(overlap) / len(selected | active)
            examples.append((similarity, row_no, overlap))
        if not examples:
            continue
        examples.sort(key=lambda item: (-item[0], item[1]))
        nearest = examples[:5]
        by_disease[disease] = {
            'score': sum(item[0] for item in nearest) / len(nearest),
            'best': examples[0][0],
            'matched': examples[0][2],
            'rows': [item[1] for item in nearest],
        }

    ranked = sorted(by_disease.items(), key=lambda item: (-item[1]['score'], -item[1]['best'], item[0]))[:3]
    total = sum(item[1]['score'] for item in ranked)
    precaution_rows = {r.get('Disease', '').strip(): [r.get(f'Precaution_{i}', '').strip()
                        for i in range(1, 5) if r.get(f'Precaution_{i}', '').strip()]
                       for r in read_csv(PRECAUTIONS)} if PRECAUTIONS.exists() else {}
    descriptions = {r.get('Disease', '').strip(): r.get('Description', '').strip()
                    for r in read_csv(DESCRIPTIONS)} if DESCRIPTIONS.exists() else {}

    predictions = []
    for disease, evidence in ranked:
        predictions.append({
            'name': disease,
            'score': round(evidence['score'], 8),
            'score_percent': round(evidence['score'] * 100 / total, 1) if total else 0,
            'match_percent': round(evidence['best'] * 100, 1),
            'matched_symptoms': sorted(evidence['matched']),
            'description': descriptions.get(disease, ''),
            'precautions': precaution_rows.get(disease, []),
            'source': 'Training.csv' if disease else '',
            'precautions_source': 'symptom_precaution.csv' if precaution_rows.get(disease) else None,
        })
    return {'predictions': predictions, 'unknown_symptoms': unknown,
            'disclaimer': DISCLAIMER,
            'matching_method': 'Jaccard similarity averaged over the five nearest distinct profiles per disease in Training.csv'}


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            self.send_json({'status': 'ok', 'service': 'medibot-model',
                            'symptoms': len(catalog()), 'dataset': 'Training.csv'})
        elif self.path == '/symptoms':
            self.send_json(catalog_with_counts())
        else:
            self.send_json({'error': 'not found'}, 404)

    def do_POST(self):
        if self.path != '/predict':
            self.send_json({'error': 'not found'}, 404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length) or b'{}')
            self.send_json(predict(payload))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json({'error': 'invalid_request', 'detail': str(exc)}, 400)

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
