from pathlib import Path
import hashlib, json, sqlite3, base64
import streamlit as st

BASE = Path(__file__).parent
DB = BASE / 'medibot_mali.sqlite3'
HERO = BASE / 'assets' / 'hero-clinic.png'

def pw(value): return hashlib.sha256(value.encode()).hexdigest()
def connect():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
def query(sql, args=(), one=False):
    with connect() as c:
        cur = c.execute(sql, args); rows = cur.fetchall(); c.commit()
    return rows[0] if one and rows else (None if one else rows)
def audit(user_id, action, entity, entity_id=None):
    query('INSERT INTO audit(user_id,action,entity,entity_id) VALUES(?,?,?,?)', (user_id,action,entity,entity_id))

def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS hospitals(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,city TEXT,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT,hospital_id INTEGER,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,password TEXT,hospital_id INTEGER,created_by INTEGER,active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS analyses(id INTEGER PRIMARY KEY AUTOINCREMENT,patient_id INTEGER,staff_id INTEGER,symptoms TEXT,predictions TEXT,status TEXT DEFAULT 'submitted',created_at TEXT DEFAULT CURRENT_TIMESTAMP,medical_response TEXT,lab_request TEXT,prescription TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT,entity TEXT,entity_id INTEGER,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS symptom_feedback(id INTEGER PRIMARY KEY AUTOINCREMENT,symptom TEXT UNIQUE,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        if not c.execute("SELECT 1 FROM users WHERE email='admin@medibot.local'").fetchone():
            c.execute("INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)", ('Administrateur','admin@medibot.local',pw('Admin123!'),'admin'))
        h = c.execute("SELECT id FROM hospitals WHERE name='Hôpital Gabriel Touré'").fetchone()
        if not h:
            c.execute("INSERT INTO hospitals(name,city) VALUES('Hôpital Gabriel Touré','Bamako')"); h=c.execute("SELECT id FROM hospitals WHERE name='Hôpital Gabriel Touré'").fetchone()
        defaults=[('Gabriel TOURE','directeur@medibot.local','director'),('Dr. Awa Traoré','generaliste@medibot.local','doctor'),('Dr. Moussa Diarra','specialiste@medibot.local','specialist'),('Fatoumata Coulibaly','infirmiere@medibot.local','nurse')]
        for n,e,r in defaults: c.execute("INSERT OR IGNORE INTO users(name,email,password,role,hospital_id) VALUES(?,?,?,?,?)",(n,e,pw('Demo123!'),r,h[0]))
        c.execute("INSERT OR IGNORE INTO patients(name,email,password,hospital_id,created_by) VALUES(?,?,?,?,?)",('Patient Démonstration','patient@medibot.local',pw('Demo123!'),h[0],1))

@st.cache_data
def symptoms_catalog():
    raw=['high_fever','cough','headache','fatigue','nausea','vomiting','diarrhoea','body_pain','chills','sore_throat','runny_nose','abdominal_pain','dizziness','skin_rash','joint_pain','loss_of_appetite','back_pain','breathlessness','chest_pain','weakness']
    labels=[]
    for s in raw: labels.append((s.replace('_',' '),s))
    return labels, raw
def predict(selected):
    return []
def normalize(s): return s.lower().replace('_',' ')

def styles():
    hero_bg = ''
    if HERO.exists():
        hero_bg = 'data:image/png;base64,' + base64.b64encode(HERO.read_bytes()).decode()
    st.markdown('''<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
    :root{--deep:#073d37;--green:#078562;--mint:#e8f8f2;--soft:#b6e8d7;--teal:#43b99a}
    .stApp{background:#fbfefd;color:#073d37;font-family:'DM Sans',sans-serif}.block-container{max-width:1280px;padding:1.5rem 3.5rem 4rem}
    h1,h2,h3{font-family:'Playfair Display',serif;color:var(--deep)!important}.brand{font-family:'Playfair Display',serif;color:var(--deep);font-size:24px}
    .hero{border-radius:30px;background:linear-gradient(110deg,rgba(232,248,242,.96) 0%,rgba(255,255,255,.92) 48%,rgba(182,232,215,.45) 100%);padding:58px 54px;min-height:390px;box-shadow:0 16px 50px #073d3712;position:relative;overflow:hidden}
    .hero:after{content:'';position:absolute;inset:0;background:linear-gradient(90deg,rgba(255,255,255,.9) 0 42%,transparent 70%),url('''' + hero_bg + '''') right center/auto 100% no-repeat;opacity:.82;pointer-events:none}.hero>*{position:relative;z-index:1;max-width:520px}.hero h1{font-size:54px;line-height:1.02;margin:10px 0 18px}.hero p{font-size:18px;line-height:1.6;color:#325e51}.eyebrow{color:var(--green);font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:12px}
    .card{background:#fff;border:1px solid #d7eee5;border-radius:22px;padding:26px;min-height:170px;box-shadow:0 8px 28px #073d370c}.icon{font-size:28px;background:var(--mint);width:54px;height:54px;border-radius:16px;display:grid;place-items:center}.step{display:flex;gap:18px;align-items:flex-start}.num{color:#fff;background:var(--green);border-radius:50%;width:34px;height:34px;display:grid;place-items:center;font-weight:700;flex:none}.quote{background:var(--deep);color:white;border-radius:28px;padding:38px 44px}.quote h2{color:white!important}.stButton>button{border-radius:12px;border:1px solid #0b8c6a;background:white;color:var(--deep);font-weight:700}.stButton>button:hover{background:var(--mint);border-color:var(--green)}
    [data-testid='stMetricValue']{color:var(--green)}
    </style>''', unsafe_allow_html=True)

def nav():
    cols=st.columns([2.3,1,1,1,1.2])
    cols[0].markdown('<div class="brand">✚ Medibot Mali</div><small>La santé, mieux coordonnée.</small>',unsafe_allow_html=True)
    for col,label,page in zip(cols[1:],['Accueil','À propos','Contact','Connexion'],['home','about','contact','login']):
        if col.button(label,use_container_width=True): st.session_state.page=page; st.rerun()
def public():
    nav(); page=st.session_state.get('page','home')
    if page=='login': login(); return
    if page=='about':
        st.markdown('<div class="hero"><div class="eyebrow">Notre mission</div><h1>Le soin commence par une meilleure coordination.</h1><p>Medibot Mali facilite le parcours entre patient, hôpital, médecin, spécialiste et laboratoire, avec des droits d’accès pensés pour chaque rôle.</p></div>',unsafe_allow_html=True)
        st.subheader('Les bénéfices pour le Mali'); cols=st.columns(3)
        for c,icon,title,text in zip(cols,['◈','↗','⌁'],['Un dossier qui suit le patient','Moins de déplacements','Une équipe connectée'],['Historique, analyses et recommandations réunis dans un même parcours.','Le patient transmet ses symptômes et documents à distance.','Chaque professionnel autorisé reçoit l’information utile au bon moment.']): c.markdown(f'<div class="card"><div class="icon">{icon}</div><h3>{title}</h3><p>{text}</p></div>',unsafe_allow_html=True)
        return
    if page=='contact':
        st.markdown('<div class="hero"><div class="eyebrow">Nous écrire</div><h1>Une question sur votre établissement ?</h1><p>Medibot Mali est conçu pour évoluer avec les hôpitaux et les régions du Mali.</p></div>',unsafe_allow_html=True); st.info('Les comptes sont créés par l’administrateur ou le responsable de votre hôpital.'); return
    st.markdown('<div class="hero"><div class="eyebrow">Santé numérique au Mali</div><h1>Votre santé, mieux suivie.</h1><p>Un parcours numérique simple pour transmettre vos symptômes, coordonner les soins et garder une trace des recommandations validées.</p></div>',unsafe_allow_html=True)
    st.write(''); st.subheader('Un parcours simple, pensé pour l’humain'); cols=st.columns(4)
    for c,n,t,desc in zip(cols,['01','02','03','04'],['Le patient signale','Le professionnel analyse','Le laboratoire intervient','Le patient reçoit'],['Symptômes, photo ou document.','Une première orientation aide le médecin.','Les examens sont suivis dans le dossier.','Réponse, recommandation et documents validés.']): c.markdown(f'<div class="card step"><div class="num">{n}</div><div><h3>{t}</h3><p>{desc}</p></div></div>',unsafe_allow_html=True)
    st.write(''); st.subheader('Des services pensés pour chaque étape'); services=st.columns(4)
    for c,icon,title,desc in zip(services,['⌁','✚','◈','▣'],['Conseils de santé','Prévention','Orientation médicale','Bien-être'],['Des informations simples et utiles.','Adopter les bons réflexes au quotidien.','Être orienté vers le bon professionnel.','Un suivi plus serein et plus humain.']): c.markdown(f'<div class="card"><div class="icon">{icon}</div><h3>{title}</h3><p>{desc}</p></div>',unsafe_allow_html=True)
    st.write(''); st.markdown('<div class="quote"><h2>La technologie au service de la continuité des soins.</h2><p>Une plateforme claire pour rapprocher les patients, les professionnels et les établissements de santé.</p></div>',unsafe_allow_html=True)

def login():
    st.title('Connexion à votre espace'); st.caption('Les comptes sont créés par l’administrateur ou le responsable de l’hôpital.')
    with st.form('login'):
        email=st.text_input('Adresse e-mail'); password=st.text_input('Mot de passe',type='password'); ok=st.form_submit_button('Se connecter',type='primary')
    if ok:
        u=query('SELECT * FROM users WHERE email=? AND password=? AND active=1',(email,pw(password)),True); p=query('SELECT * FROM patients WHERE email=? AND password=? AND active=1',(email,pw(password)),True)
        if u: st.session_state.user=dict(u); audit(u['id'],'login','user',u['id']); st.rerun()
        elif p: st.session_state.user={**dict(p),'role':'patient'}; st.rerun()
        else: st.error('Identifiants invalides ou compte désactivé.')
    st.markdown('''<div class="card"><h3>Comptes de démonstration</h3><p><b>Administrateur</b><br><code>admin@medibot.local</code><br><code>Admin123!</code></p><p><b>Responsable d’hôpital</b><br><code>directeur@medibot.local</code><br><code>Demo123!</code></p><p><b>Généraliste</b><br><code>generaliste@medibot.local</code><br><code>Demo123!</code></p><p><b>Spécialiste</b><br><code>specialiste@medibot.local</code><br><code>Demo123!</code></p><p><b>Infirmière</b><br><code>infirmiere@medibot.local</code><br><code>Demo123!</code></p><p><b>Patient</b><br><code>patient@medibot.local</code><br><code>Demo123!</code></p></div>''',unsafe_allow_html=True)

def sidebar(u):
    st.sidebar.markdown('## ✚ Medibot Mali'); st.sidebar.caption(f"{u['name']} · {u['role']}")
    if st.sidebar.button('Se déconnecter'): st.session_state.pop('user',None); st.session_state.page='home'; st.rerun()

def admin(u):
    st.title('Pilotage de la plateforme'); hs=query('SELECT * FROM hospitals'); staff=query("SELECT * FROM users WHERE role!='admin'"); pats=query('SELECT * FROM patients'); analyses=query('SELECT * FROM analyses')
    a,b,c,d=st.columns(4); a.metric('Hôpitaux',len(hs)); b.metric('Personnel',len(staff)); c.metric('Patients',len(pats)); d.metric('Analyses',len(analyses))
    t1,t2,t3=st.tabs(['Hôpitaux','Comptes du personnel','Journal d’audit'])
    with t1:
        with st.form('hospital'):
            n=st.text_input('Nom'); city=st.text_input('Ville',value='Bamako'); save=st.form_submit_button('Créer l’hôpital')
        if save and n: query('INSERT INTO hospitals(name,city) VALUES(?,?)',(n,city)); st.rerun()
        st.dataframe([dict(x) for x in hs],use_container_width=True)
    with t2:
        st.info('Le responsable d’hôpital crée les comptes métier dans son établissement.'); st.dataframe([dict(x) for x in staff],use_container_width=True)
    with t3: st.dataframe([dict(x) for x in query('SELECT * FROM audit ORDER BY id DESC LIMIT 100')],use_container_width=True)

def director(u):
    st.title('Espace responsable d’hôpital'); st.write('Créez et gérez les comptes de votre établissement.'); hs=query('SELECT name FROM hospitals WHERE id=?',(u['hospital_id'],),True); st.info(f"Établissement : {hs['name'] if hs else '—'}")
    with st.form('staff'):
        n=st.text_input('Nom complet'); e=st.text_input('E-mail'); role=st.selectbox('Fonction',['doctor','specialist','nurse','caregiver','laboratory']); p=st.text_input('Mot de passe initial',type='password'); save=st.form_submit_button('Créer le compte')
    if save and n and e and p: query('INSERT INTO users(name,email,password,role,hospital_id) VALUES(?,?,?,?,?)',(n,e,pw(p),role,u['hospital_id'])); audit(u['id'],'create','user'); st.success('Compte créé.'); st.rerun()
    st.dataframe([dict(x) for x in query('SELECT name,email,role,active FROM users WHERE hospital_id=?',(u['hospital_id'],))],use_container_width=True)

def staff(u):
    st.title('Espace personnel de santé'); rows=query('SELECT a.*,p.name patient_name FROM analyses a JOIN patients p ON p.id=a.patient_id WHERE p.hospital_id=? AND (a.staff_id=? OR a.staff_id IS NULL)',(u['hospital_id'],u['id'])); st.metric('Demandes à traiter',len(rows))
    with st.expander('Créer un dossier patient'):
        with st.form('patient'):
            n=st.text_input('Nom'); e=st.text_input('E-mail'); p=st.text_input('Mot de passe initial',type='password'); save=st.form_submit_button('Créer le dossier')
        if save and n and e and p: query('INSERT INTO patients(name,email,password,hospital_id,created_by) VALUES(?,?,?,?,?)',(n,e,pw(p),u['hospital_id'],u['id'])); st.success('Dossier créé.'); st.rerun()
    for r in rows:
        with st.container(border=True):
            st.write(f"**{r['patient_name']}** · {r['created_at']} · {r['status']}"); st.caption('Symptômes : '+r['symptoms'])
            if r['predictions']: st.warning('Hypothèses réservées au personnel : '+', '.join(json.loads(r['predictions'])))
            response=st.text_area('Réponse médicale validée',value=r['medical_response'] or '',key='r'+str(r['id'])); lab=st.text_input('Demande laboratoire',value=r['lab_request'] or '',key='l'+str(r['id'])); prescription=st.text_input('Recommandation / ordonnance',value=r['prescription'] or '',key='p'+str(r['id']))
            if st.button('Enregistrer et transmettre',key='save'+str(r['id'])): query('UPDATE analyses SET staff_id=?,status="reviewed",medical_response=?,lab_request=?,prescription=? WHERE id=?',(u['id'],response,lab,prescription,r['id'])); audit(u['id'],'update','analysis',r['id']); st.rerun()

def patient(u):
    st.title('Mon espace patient'); st.info('Décrivez vos symptômes pour transmettre une demande à votre équipe médicale. Un professionnel validera votre réponse.')
    labels,raw=symptoms_catalog(); common=['high_fever','cough','headache','fatigue','nausea','vomiting','diarrhoea','body_pain']
    common=[x for x in common if x in raw]; selected=st.multiselect('Symptômes fréquents',common,format_func=lambda x:x.replace('_',' '))
    search=st.text_input('Rechercher un autre symptôme',placeholder='Ex. fièvre, démangeaisons…')
    matches=[(label,key) for label,key in labels if normalize(search) in normalize(label)][:10] if search else []
    if matches: st.caption('Suggestions : '+ ' · '.join(x[0] for x in matches))
    chosen_extra=st.selectbox('Sélectionner une suggestion', ['—']+[x[1] for x in matches], format_func=lambda x: next((a for a,b in matches if b==x),x)) if matches else '—'
    if chosen_extra!='—' and chosen_extra not in selected: selected.append(chosen_extra)
    details=st.text_area('Précisions ou symptôme absent du catalogue'); upload=st.file_uploader('Joindre une photo ou un document',type=['png','jpg','jpeg','pdf']); camera=st.camera_input('Prendre une photo')
    if st.button('Lancer l’analyse et transmettre',type='primary') and (selected or details or upload or camera):
        unknown=details.strip() if details.strip() else ''
        if unknown: query('INSERT OR IGNORE INTO symptom_feedback(symptom) VALUES(?)',(unknown,))
        attachment=upload.name if upload else ('photo_camera' if camera else '')
        text='; '.join(selected)+(f". {details}" if details else '')+(f". Pièce jointe: {attachment}" if attachment else '')
        query('INSERT INTO analyses(patient_id,symptoms,predictions) VALUES(?,?,?)',(u['id'],text,json.dumps([],ensure_ascii=False))); st.success('Demande transmise à votre équipe médicale.'); st.rerun()
    st.subheader('Mon historique');
    for r in query('SELECT * FROM analyses WHERE patient_id=? ORDER BY id DESC',(u['id'],)):
        with st.container(border=True):
            st.write(f"**{r['created_at']}** · {r['status']}"); st.caption(r['symptoms'])
            if r['status']=='reviewed': st.success(r['medical_response'] or 'Réponse validée disponible.'); st.write('Recommandation :',r['prescription'] or '—'); st.write('Laboratoire :',r['lab_request'] or '—')

init(); styles()
if 'user' not in st.session_state: public()
else:
    u=st.session_state.user; sidebar(u)
    {'admin':admin,'director':director,'doctor':staff,'specialist':staff,'nurse':staff,'caregiver':staff,'laboratory':staff,'patient':patient}[u['role']](u)
