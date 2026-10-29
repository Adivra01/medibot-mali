from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os, re
import json, sqlite3, urllib.request, base64, binascii
from urllib.parse import quote

ROOT = Path(__file__).parent
DB = ROOT.parent / 'medibot_mali.sqlite3'
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def audit(c, action, entity, entity_id):
    c.execute('CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,entity TEXT,entity_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    c.execute('INSERT INTO audit(action,entity,entity_id) values(?,?,?)',(action,entity,entity_id))
def state():
    with db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS patient_assignments(patient_id INTEGER, staff_id INTEGER, active INTEGER DEFAULT 1, UNIQUE(patient_id,staff_id))')
        c.execute('CREATE TABLE IF NOT EXISTS lab_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,analysis_id INTEGER,patient_id INTEGER,staff_id INTEGER,exam_type TEXT,notes TEXT,status TEXT DEFAULT "requested",result TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS medical_notes(id INTEGER PRIMARY KEY AUTOINCREMENT,analysis_id INTEGER,staff_id INTEGER,note TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS case_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,analysis_id INTEGER NOT NULL,patient_id INTEGER NOT NULL,sender_id INTEGER,sender_role TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        c.execute('CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY AUTOINCREMENT,patient_id INTEGER NOT NULL,analysis_id INTEGER,lab_request_id INTEGER,uploader_id INTEGER,category TEXT NOT NULL,filename TEXT NOT NULL,media_type TEXT NOT NULL,data BLOB NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
        if 'phone' not in [r['name'] for r in c.execute('pragma table_info(users)')]: c.execute('ALTER TABLE users ADD COLUMN phone TEXT')
        if 'phone' not in [r['name'] for r in c.execute('pragma table_info(patients)')]: c.execute('ALTER TABLE patients ADD COLUMN phone TEXT')
        if 'priority' not in [r['name'] for r in c.execute('pragma table_info(analyses)')]: c.execute('ALTER TABLE analyses ADD COLUMN priority TEXT')
        if 'unknown_symptoms' not in [r['name'] for r in c.execute('pragma table_info(analyses)')]: c.execute('ALTER TABLE analyses ADD COLUMN unknown_symptoms TEXT DEFAULT "[]"')
        patient=c.execute("select id from patients where email='patient@medibot.local'").fetchone()
        staff=c.execute("select id from users where email in ('generaliste@medibot.local','specialiste@medibot.local','infirmiere@medibot.local')").fetchall()
        if patient:
            for row in staff: c.execute('INSERT OR IGNORE INTO patient_assignments(patient_id,staff_id) values(?,?)',(patient['id'],row['id']))
        hospitals=[dict(x) for x in c.execute('select id,name,city,active from hospitals order by id')]
        users=[dict(x) for x in c.execute('select id,name,email,phone,role,hospital_id,active from users order by id')]
        patients=[dict(x) for x in c.execute('select id,name,email,phone,hospital_id,active from patients order by id')]
        analyses=[dict(x) for x in c.execute('select id,patient_id,staff_id,symptoms,predictions,unknown_symptoms,status,created_at,medical_response,lab_request,prescription,priority from analyses order by id desc')]
        assignments=[dict(x) for x in c.execute('select patient_id,staff_id,active from patient_assignments')]
        labs=[dict(x) for x in c.execute('select * from lab_requests order by id desc')]
        notes=[dict(x) for x in c.execute('select * from medical_notes order by id desc')]
        messages=[dict(x) for x in c.execute("select m.*,case when m.sender_role='patient' then p.name else u.name end as sender_name from case_messages m left join patients p on m.sender_role='patient' and p.id=m.sender_id left join users u on m.sender_role!='patient' and u.id=m.sender_id order by m.created_at,m.id")]
        documents=[dict(x) for x in c.execute('select id,patient_id,analysis_id,lab_request_id,uploader_id,category,filename,media_type,length(data) as size,created_at from documents order by id desc')]
        activities=[dict(x) for x in c.execute('select id,user_id,action,entity,entity_id,created_at from audit order by id desc limit 200')]
    return {'hospitals':hospitals,'users':users,'patients':patients,'analyses':analyses,'assignments':assignments,'labs':labs,'notes':notes,'messages':messages,'documents':documents,'audit':activities}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs): super().__init__(*args, directory=str(ROOT), **kwargs)
    def log_message(self, *_): pass
    def send_json(self, payload, status=200):
        raw=json.dumps(payload,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if self.path.startswith('/api/documents/'):
            try: document_id=int(self.path.rstrip('/').split('/')[-1])
            except ValueError: self.send_error(404); return
            with db() as c: item=c.execute('select filename,media_type,data from documents where id=?',(document_id,)).fetchone()
            if not item: self.send_error(404); return
            raw=bytes(item['data']); self.send_response(200); self.send_header('Content-Type',item['media_type']); self.send_header('Content-Length',str(len(raw))); self.send_header('Content-Disposition',"inline; filename*=UTF-8''"+quote(item['filename'])); self.end_headers(); self.wfile.write(raw); return
        if self.path.startswith('/api/state'):
            raw=json.dumps(state(),ensure_ascii=False).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if self.path.startswith('/api/model/symptoms'):
            self.proxy('http://127.0.0.1:8765/symptoms'); return
        super().do_GET()
    def do_POST(self):
        if self.path.startswith('/api/contact'):
            try:
                length=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(length) or b'{}')
                role=payload.get('role',''); person_id=int(payload.get('person_id') or 0); raw_phone=str(payload.get('phone','')).strip()
                digits=re.sub(r'\D','',raw_phone)
                if digits.startswith('00'): digits=digits[2:]
                if raw_phone and not raw_phone.startswith('+'): raise ValueError('Saisissez le numéro au format international, par exemple +223…')
                if raw_phone and not 8<=len(digits)<=15: raise ValueError('Le numéro international doit contenir entre 8 et 15 chiffres.')
                phone=f'+{digits}' if digits else None
                with db() as c:
                    if role=='patient':
                        exists=c.execute('select 1 from patients where id=?',(person_id,)).fetchone()
                        if not exists: self.send_error(404); return
                        c.execute('update patients set phone=? where id=?',(phone,person_id))
                    elif role in {'doctor','specialist','nurse','director'}:
                        exists=c.execute('select 1 from users where id=? and role=?',(person_id,role)).fetchone()
                        if not exists: self.send_error(404); return
                        c.execute('update users set phone=? where id=?',(phone,person_id))
                    else: self.send_error(403); return
                    audit(c,'contact_phone_updated',role,person_id)
                self.send_json({'ok':True,'phone':phone}); return
            except (ValueError,TypeError,json.JSONDecodeError) as exc:
                self.send_json({'ok':False,'error':str(exc)},400); return
        if self.path.startswith('/api/documents'):
            length=int(self.headers.get('Content-Length','0'))
            if length>12_000_000: self.send_error(413); return
            try:
                payload=json.loads(self.rfile.read(length) or b'{}')
                content=base64.b64decode(payload.get('data',''),validate=True)
                patient_id=int(payload.get('patient_id',1)); category=payload.get('category','medical_document')
                media_type=payload.get('media_type','application/octet-stream').split(';',1)[0].lower()
                filename=os.path.basename(payload.get('filename','document'))[:180]
                if not content or len(content)>8_000_000: raise ValueError('La pièce jointe doit peser moins de 8 Mo.')
                if media_type not in {'image/png','image/jpeg','image/webp','image/gif','application/pdf'}: raise ValueError('Format accepté : PNG, JPG, WEBP ou PDF.')
                if category not in {'symptom','lab_request','lab_result','prescription','medical_document','hospital_form'}: raise ValueError('Type de document invalide.')
                with db() as c:
                    if not c.execute('select 1 from patients where id=?',(patient_id,)).fetchone(): raise ValueError('Dossier patient introuvable.')
                    analysis_id=payload.get('analysis_id') or None; lab_request_id=payload.get('lab_request_id') or None
                    if analysis_id and not c.execute('select 1 from analyses where id=? and patient_id=?',(analysis_id,patient_id)).fetchone(): raise ValueError('Demande patient incohérente.')
                    if lab_request_id and not c.execute('select 1 from lab_requests where id=? and patient_id=?',(lab_request_id,patient_id)).fetchone(): raise ValueError('Fiche laboratoire incohérente.')
                    cur=c.execute('insert into documents(patient_id,analysis_id,lab_request_id,uploader_id,category,filename,media_type,data) values(?,?,?,?,?,?,?,?)',(patient_id,analysis_id,lab_request_id,payload.get('uploader_id'),category,filename,media_type,content))
                    document_id=cur.lastrowid; audit(c,'document_added','document',document_id)
                self.send_json({'ok':True,'document_id':document_id},201); return
            except (ValueError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
                self.send_json({'ok':False,'error':str(exc)},400); return
        if self.path.startswith('/api/analyses'):
            length=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(length) or b'{}')
            symptoms=payload.get('symptoms', [])
            if isinstance(symptoms, str):
                try:
                    parsed=json.loads(symptoms)
                    if isinstance(parsed,dict):
                        symptoms=parsed.get('selected',[])
                        payload['details']=parsed.get('details',payload.get('details',''))
                    else:
                        symptoms=[x.strip() for x in symptoms.split(';') if x.strip()]
                except json.JSONDecodeError:
                    symptoms=[x.strip() for x in symptoms.split(';') if x.strip()]
            symptom_record=json.dumps({'selected':symptoms,'details':payload.get('details',''),'medical_history':payload.get('medical_history','')},ensure_ascii=False)
            with db() as c:
                if 'unknown_symptoms' not in [r['name'] for r in c.execute('pragma table_info(analyses)')]: c.execute('ALTER TABLE analyses ADD COLUMN unknown_symptoms TEXT DEFAULT "[]"')
                cur=c.execute('insert into analyses(patient_id,symptoms,predictions,status,unknown_symptoms) values(?,?,?,?,?)',(payload.get('patient_id',1),symptom_record,json.dumps(payload.get('predictions',[]),ensure_ascii=False),'submitted',json.dumps(payload.get('unknown_symptoms',[]),ensure_ascii=False))); analysis_id=cur.lastrowid
                audit(c,'analysis_submitted','analysis',analysis_id)
                # Les demandes patients sont visibles par l'équipe soignante assignée.
                c.execute('CREATE TABLE IF NOT EXISTS patient_assignments(patient_id INTEGER, staff_id INTEGER, active INTEGER DEFAULT 1, UNIQUE(patient_id,staff_id))')
                for staff in c.execute("select id from users where email in ('generaliste@medibot.local','specialiste@medibot.local','infirmiere@medibot.local')").fetchall():
                    c.execute('INSERT OR IGNORE INTO patient_assignments(patient_id,staff_id) values(?,?)',(payload.get('patient_id',1),staff['id']))
            raw=json.dumps({'ok':True,'analysis_id':analysis_id},ensure_ascii=False).encode(); self.send_response(201); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if self.path.startswith('/api/analysis/'):
            length=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(length) or b'{}'); aid=int(self.path.rstrip('/').split('/')[-1])
            with db() as c:
                if payload.get('action')=='message':
                    analysis=c.execute('select a.patient_id,p.hospital_id from analyses a join patients p on p.id=a.patient_id where a.id=?',(aid,)).fetchone()
                    sender_role=payload.get('sender_role',''); message=str(payload.get('message','')).strip()
                    if not analysis or not message or len(message)>2000: self.send_error(400); return
                    if sender_role=='patient': sender_id=analysis['patient_id']
                    elif sender_role in {'doctor','specialist','nurse','director'}:
                        sender_id=int(payload.get('sender_id') or 0)
                        agent=c.execute('select id,hospital_id,role from users where id=? and active=1',(sender_id,)).fetchone()
                        assigned=c.execute('select 1 from patient_assignments where patient_id=? and staff_id=? and active=1',(analysis['patient_id'],sender_id)).fetchone()
                        if not agent or agent['hospital_id']!=analysis['hospital_id'] or agent['role']!=sender_role or (sender_role!='director' and not assigned): self.send_error(403); return
                    else: self.send_error(403); return
                    c.execute('insert into case_messages(analysis_id,patient_id,sender_id,sender_role,message) values(?,?,?,?,?)',(aid,analysis['patient_id'],sender_id,sender_role,message))
                    message_id=c.execute('select last_insert_rowid()').fetchone()[0]; audit(c,'case_message_sent','case_message',message_id)
                elif payload.get('action')=='review':
                    c.execute('update analyses set staff_id=COALESCE(staff_id,?),status=CASE WHEN status="submitted" THEN "in_progress" ELSE status END where id=?',(payload.get('staff_id'),aid))
                    audit(c,'analysis_reviewed','analysis',aid)
                elif payload.get('action')=='predictions':
                    c.execute('update analyses set predictions=?,unknown_symptoms=? where id=?',(json.dumps(payload.get('predictions',[]),ensure_ascii=False),json.dumps(payload.get('unknown_symptoms',[]),ensure_ascii=False),aid))
                    audit(c,'model_matches_refreshed','analysis',aid)
                elif payload.get('action')=='response':
                    c.execute('update analyses set staff_id=?,status="reviewed",medical_response=?,prescription=? where id=?',(payload.get('staff_id'),payload.get('response',''),payload.get('prescription',''),aid))
                    audit(c,'medical_response_saved','analysis',aid)
                elif payload.get('action')=='note':
                    c.execute('insert into medical_notes(analysis_id,staff_id,note) values(?,?,?)',(aid,payload.get('staff_id'),payload.get('note','')))
                    audit(c,'specialist_note_added','analysis',aid)
                elif payload.get('action')=='lab':
                    lab_analysis=aid or payload.get('analysis_id')
                    c.execute('insert into lab_requests(analysis_id,patient_id,staff_id,exam_type,notes) values(?,?,?,?,?)',(lab_analysis,payload.get('patient_id'),payload.get('staff_id'),payload.get('exam_type',''),payload.get('notes','')))
                    lab_id=c.execute('select last_insert_rowid()').fetchone()[0]
                    c.execute('update analyses set lab_request=? where id=?',(payload.get('exam_type',''),aid))
                    audit(c,'lab_request_created','lab_request',lab_id)
                elif payload.get('action')=='lab_result':
                    c.execute('update lab_requests set result=?,status="completed" where id=?',(payload.get('result',''),payload.get('lab_id')))
                    audit(c,'lab_result_saved','lab_request',payload.get('lab_id'))
                elif payload.get('action')=='priority':
                    priority=payload.get('priority')
                    if priority not in {'À évaluer','Basse','Normale','Élevée','Urgente'}: self.send_error(400); return
                    c.execute('update analyses set priority=? where id=?',(priority,aid)); audit(c,'clinical_priority_set','analysis',aid)
                elif payload.get('action')=='status':
                    status=payload.get('status')
                    if status not in {'submitted','in_progress','reviewed','treated','closed'}: self.send_error(400); return
                    current=c.execute('select status from analyses where id=?',(aid,)).fetchone()
                    if not current: self.send_error(404); return
                    order={'submitted':0,'in_progress':1,'reviewed':2,'treated':3,'closed':4}
                    if order[status] < order.get(current['status'],0): self.send_error(409); return
                    pending_lab=c.execute('select 1 from lab_requests where analysis_id=? and status!="completed" limit 1',(aid,)).fetchone()
                    if status in {'treated','closed'} and pending_lab: self.send_error(409); return
                    c.execute('update analyses set status=? where id=?',(status,aid)); audit(c,'analysis_status_changed','analysis',aid)
            raw=json.dumps({'ok':True},ensure_ascii=False).encode(); self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if self.path.startswith('/api/model/predict'):
            length=int(self.headers.get('Content-Length','0')); body=self.rfile.read(length)
            self.proxy('http://127.0.0.1:8765/predict', body); return
        self.send_error(404)
    def proxy(self,url,body=None):
        try:
            req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'} if body else {})
            with urllib.request.urlopen(req,timeout=5) as response: raw=response.read(); status=response.status
            self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
        except Exception as exc:
            raw=json.dumps({'error':'model_unavailable','detail':str(exc)}).encode(); self.send_response(503); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)

if __name__ == '__main__':
    os.chdir(ROOT)
    ThreadingHTTPServer(('127.0.0.1', 3000), Handler).serve_forever()
