from dotenv import load_dotenv
load_dotenv()
import os
import re
import json
import random
import hashlib
import io
from datetime import datetime, timedelta
import pymysql
from flask import Flask, render_template, request, jsonify, send_file,session
from openai import OpenAI
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import boto3
from botocore.exceptions import NoCredentialsError
from fpdf import FPDF
import requests

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "govconnect_free_secure_session_token_19283")

# ══════════════════════════════════════════
#  EXTERNAL SERVICE CONFIGURATIONS
# ══════════════════════════════════════════
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY") or "dummy-key"
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)
FREE_MODEL = "openrouter/free"

# AWS S3 Cloud Storage Engine Setup
S3_BUCKET = os.environ.get("AWS_S3_BUCKET_NAME")
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID") or "dummy",
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or "dummy"
)

# ══════════════════════════════════════════
#  MYSQL CONFIGURATION ENGINE
#  Supports Railway's MYSQL_URL or individual variables
# ══════════════════════════════════════════
import urllib.parse

def get_db_connection():
    # Railway provides MYSQL_URL — use it directly if available
    mysql_url = os.environ.get("MYSQL_URL") or os.environ.get("MYSQL_PUBLIC_URL")
    if mysql_url:
        # Parse the URL: mysql://user:password@host:port/dbname
        parsed = urllib.parse.urlparse(mysql_url)
        return pymysql.connect(
            host=parsed.hostname,
            port=parsed.port or 3306,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip('/'),
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
    # Fallback to individual environment variables
    return pymysql.connect(
        host=os.environ.get("MYSQLHOST") or os.environ.get("MYSQL_HOST", "localhost"),
        port=int(os.environ.get("MYSQLPORT") or os.environ.get("MYSQL_PORT") or 3306),
        user=os.environ.get("MYSQLUSER") or os.environ.get("MYSQL_USER", "root"),
        password=os.environ.get("MYSQLPASSWORD") or os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ.get("MYSQLDATABASE") or os.environ.get("MYSQL_DB", "railway"),
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10
    )

def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Citizens Table (Enhanced with Verification Matrix Parameters)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS citizens (
                    mobile VARCHAR(15) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL ,
                    email VARCHAR(100) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    state VARCHAR(50) NOT NULL,
                    dob VARCHAR(20) NOT NULL,
                    aadhaar VARCHAR(20) NOT NULL,
                    is_verified TINYINT(1) DEFAULT 0,
                    otp_hash VARCHAR(255) DEFAULT NULL,
                    otp_expiry TIMESTAMP NULL DEFAULT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            
            # 2. Officials Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS officials (
                    email VARCHAR(100) NOT NULL,
                    empid VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    desig VARCHAR(100) NOT NULL,
                    phone VARCHAR(20) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    state VARCHAR(50) NOT NULL,
                    district VARCHAR(50) NOT NULL,
                    depts TEXT NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            
            # 3. Complaints Table (Enhanced with GIS, Language, and Cloud Media Trackers)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS complaints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ref_id VARCHAR(20) UNIQUE NOT NULL,
    citizen_mobile VARCHAR(15),

    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(150) NOT NULL,

    department VARCHAR(100),

    assigned_to VARCHAR(100),

    priority VARCHAR(20),

    status VARCHAR(30)
        DEFAULT 'Pending',

    attachment_path VARCHAR(255),

    created_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMP
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,

    resolved_at TIMESTAMP NULL
);
            ''')

            # 4. Audit Logs Table (Immutable Log Stream System)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    actor VARCHAR(100) NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    target_ref VARCHAR(50) DEFAULT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
        conn.commit()
        print("💾 Enterprise Relational Schema compiled successfully.")
    finally:
        conn.close()

init_db()

# ══════════════════════════════════════════
#  UTILITY INFRASTRUCTURE PIPELINES
# ══════════════════════════════════════════
def send_real_otp(phone, otp):
    api_key = os.environ.get("FAST2SMS_API_KEY")
    if not api_key:
        print(f"[DEV MODE] OTP for {phone}: {otp}")
        return True

    url = "https://www.fast2sms.com/dev/bulkV2"
    try:
        response = requests.post(url,
            json={
                "variables_values": otp,
                "route": "otp",
                "numbers": phone
            },
            headers={"authorization": api_key},
            timeout=10
        )
        result = response.json()
        print(f"[FAST2SMS RESPONSE] status={response.status_code} body={result}")
        return result.get("return", False)
    except requests.exceptions.Timeout:
        print(f"[FAST2SMS ERROR] Request timed out for {phone}")
        return False
    except Exception as e:
        print(f"[FAST2SMS ERROR] {e}")
        return False

def upload_to_storage_service(file_obj):
    filename = secure_filename(file_obj.filename)
    if S3_BUCKET:
        try:
            s3_client.upload_fileobj(file_obj, S3_BUCKET, filename, ExtraArgs={"ACL": "public-read"})
            return f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"
        except NoCredentialsError:
            pass
    
    # Dynamic Local Storage Fallback Subsystem
    local_dir = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, filename)
    file_obj.save(local_path)
    return f"/static/uploads/{filename}"

# ══════════════════════════════════════════
#  ROUTING ENGINE & CORE API HOOKS
# ══════════════════════════════════════════
@app.route('/')
def index():
    return render_template('govconnect.html')

@app.route('/api/reverse-geocode', methods=['GET'])
def reverse_geocode():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return jsonify({"error": "lat and lon are required"}), 400

    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "json", "lat": lat, "lon": lon, "zoom": 16, "addressdetails": 1},
            headers={"User-Agent": "GovConnect-CivicApp/1.0"},
            timeout=5
        )
        data = res.json()
        address = data.get("address", {})

        parts = [
            address.get("neighbourhood") or address.get("suburb") or address.get("locality"),
            address.get("road"),
            address.get("city") or address.get("town") or address.get("village"),
            address.get("state_district"),
            address.get("state")
        ]
        place_name = ", ".join([p for p in parts if p]) or data.get("display_name")

        return jsonify({"success": True, "place_name": place_name, "raw": data.get("display_name")})
    except Exception as e:
        return jsonify({"error": "Reverse geocoding failed", "details": str(e)}), 500

@app.route('/api/auth/citizen-signup', methods=['POST'])
def citizen_signup():
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1 FROM citizens WHERE mobile = %s', (data['mobile'],))
            if cursor.fetchone():
                return jsonify({"error": "Mobile number already registered."}), 400
            
            sql = '''INSERT INTO citizens (mobile, name, email, password, state, dob, aadhaar, is_verified)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, 0)'''
            hashed_pw = generate_password_hash(data['password'])
            cursor.execute(sql,(data['mobile'],data['name'],data['email'],hashed_pw,data['state'],data['dob'],data['aadhaar']))
            
            cursor.execute('INSERT INTO audit_logs (actor, action, details) VALUES (%s, %s, %s)', 
                           (data['mobile'], "CITIZEN_SIGNUP", "Account created successfully. Awaiting OTP challenge verification."))
        conn.commit()
        return jsonify({"success": True, "user": {"name": data['name'], "mobile": data['mobile'], "email": data['email'], "is_verified": 0}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/auth/aadhaar-trigger-otp', methods=['POST'])
def trigger_otp():
    data = request.json
    mobile = data.get('mobile')
    otp_code = str(random.randint(100000, 999999))
    otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
    expiry = datetime.now() + timedelta(minutes=10)
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('UPDATE citizens SET otp_hash = %s, otp_expiry = %s WHERE mobile = %s', (otp_hash, expiry, mobile))
        conn.commit()
        send_real_otp(mobile, f"GovConnect Aadhaar Security Verification PIN: {otp_code}. Valid for 10 minutes.")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/auth/aadhaar-verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    mobile = data.get('mobile')
    otp_input = data.get('otp')
    input_hash = hashlib.sha256(otp_input.encode()).hexdigest()
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT otp_hash, otp_expiry, name, email FROM citizens WHERE mobile = %s', (mobile,))
            user = cursor.fetchone()
            if not user or user['otp_hash'] != input_hash or datetime.now() > user['otp_expiry']:
                return jsonify({"error": "Invalid or expired authorization token."}), 401
            
            cursor.execute('UPDATE citizens SET is_verified = 1, otp_hash = NULL, otp_expiry = NULL WHERE mobile = %s', (mobile,))
            cursor.execute('INSERT INTO audit_logs (actor, action, details) VALUES (%s, %s, %s)', 
                           (mobile, "AADHAAR_MFA_SUCCESS", "Aadhaar Identity Verification successful via OTP protocol."))
        conn.commit()
        return jsonify({"success": True, "user": {"name": user['name'], "mobile": mobile, "email": user['email'], "is_verified": 1}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/auth/citizen-login', methods=['POST'])
def citizen_login():
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = ' SELECT * FROM citizens WHERE mobile=%s OR email=%s'
            cursor.execute(sql,(data['username'], data['username']))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'],data['password']):
                return jsonify({"success": True,"user": {"name": user['name'],"mobile": user['mobile'],"email": user['email']
               
        }
    })
        return jsonify({"error": "Invalid login credentials."}), 401
    finally:
        conn.close()
        
@app.route('/api/auth/official-signup', methods=['POST'])
@app.route('/api/auth/official-signup', methods=['POST'])
def official_signup():
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT 1 FROM officials WHERE email = %s', (data['email'],))
            if cursor.fetchone():
                return jsonify({"error": "Official identity already initialized inside tracking arrays."}), 400
            
            # SAFE CHECK: Make sure depts is wrapped as a list if it comes as a string
            incoming_depts = data.get('depts', [])
            if isinstance(incoming_depts, str):
                incoming_depts = [incoming_depts]

            sql = '''INSERT INTO officials (email, empid, name, desig, phone, password, state, district, depts)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)'''
            hashed_pw = generate_password_hash(data['password'])
            
            cursor.execute(sql, (
                data['email'], 
                data['empid'], 
                data['name'], 
                data['desig'], 
                data['phone'], 
                hashed_pw, 
                data.get('state', 'Telangana'), 
                data.get('district', 'Default'), 
                json.dumps(incoming_depts)
            ))
            cursor.execute('INSERT INTO audit_logs (actor, action, details) VALUES (%s, %s, %s)', 
                           (data['email'], "OFFICIAL_REGISTRATION", f"Official profile created for jurisdiction district: {data.get('district', 'Default')}"))
        conn.commit()
        return jsonify({"success": True, "user": {"name": data['name'], "desig": data['desig'], "email": data['email'], "district": data.get('district', 'Default'), "depts": incoming_depts}})
    except Exception as e:
        # Return the precise database error message to your browser console for debugging
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/auth/official-login', methods=['POST'])
def official_login():
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = 'SELECT * FROM officials WHERE email=%s OR empid=%s'
            cursor.execute(sql, (data['username'], data['username']))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], data['password']):
                return jsonify({
                    "success": True, 
                    "user": {
                        "name": user['name'], "desig": user['desig'], "email": user['email'], 
                        "district": user['district'], "depts": json.loads(user['depts'])
                    }
                })
        return jsonify({"error": "Invalid official credentials."}), 401
    finally:
        conn.close()

# ══════════════════════════════════════════
#  COMPLAINTS pipeline EXECUTIONS
# ══════════════════════════════════════════
@app.route('/api/complaints/submit', methods=['POST'])
def submit_complaint():
    # Supports multipart/form-data payloads to process uploaded document frames dynamically
    payload = request.form if request.form else request.json
    ref_id = f"GC-{os.urandom(3).hex().upper()}"
    
    attachment_url = None
    if 'file' in request.files:
        attachment_url = upload_to_storage_service(request.files['file'])
    elif payload.get('image'):
        attachment_url = payload.get('image') # handles base64 passdowns from UI configurations

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = '''INSERT INTO complaints (ref_id, citizen_mobile, title, description, location, 
                                             latitude, longitude, department, official_title, official_name, priority, lang, attachment_url)
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'''
            cursor.execute(sql, (
                ref_id, payload.get('mobile'), payload['title'], payload['description'], payload['location'],
                payload.get('latitude') if payload.get('latitude') else None,
                payload.get('longitude') if payload.get('longitude') else None,
                payload['department'], payload.get('official_title'), payload.get('official_name'), 
                payload['priority'], payload.get('lang', 'en'), attachment_url
            ))
            
            cursor.execute('INSERT INTO audit_logs (actor, action, target_ref, details) VALUES (%s, %s, %s, %s)', 
                           (payload.get('mobile', 'ANONYMOUS'), "COMPLAINT_SUBMISSION", ref_id, f"Grievance recorded. Channel Language: {payload.get('lang', 'en')}"))
        conn.commit()
        send_real_otp(payload.get('mobile'), f"Grievance submitted. Reference Token ID: {ref_id}. Check status via tracking hub.")
        return jsonify({"success": True, "ref_id": ref_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/complaints')
def get_complaints():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM complaints ORDER BY created_at DESC")
            complaints = cursor.fetchall()
        return jsonify(complaints)
    finally:
        conn.close()

@app.route('/api/complaints/status/<ref_id>', methods=['GET'])
def check_complaint_status(ref_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM complaints WHERE ref_id = %s', (ref_id,))
            record = cursor.fetchone()
            if not record:
                return jsonify({"error": "Target sequence reference identifier not found"}), 404
        return jsonify({"success": True, "complaint": record})
    finally:
        conn.close()

@app.route('/api/complaints/update-status', methods=['POST'])
def update_complaint_status():
    data = request.json
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('UPDATE complaints SET status = %s WHERE ref_id = %s', (data['status'], data['ref_id']))
            cursor.execute('SELECT citizen_mobile FROM complaints WHERE ref_id = %s', (data['ref_id'],))
            row = cursor.fetchone()
            
            cursor.execute('INSERT INTO audit_logs (actor, action, target_ref, details) VALUES (%s, %s, %s, %s)', 
                           (data.get('official_email', 'OFFICIAL'), "STATUS_UPDATE", data['ref_id'], f"Status modified matrix set to: {data['status']}"))
        conn.commit()
        if row and row['citizen_mobile']:
            send_real_otp(row['citizen_mobile'], f"Status Alert: Your grievance {data['ref_id']} has been moved to '{data['status']}'.")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/analyze-issue', methods=['POST'])
def analyze_issue():
    if not OPENROUTER_KEY:
        return jsonify({"error": "Missing system configuration routing keys."}), 500
    
    data = request.json
    text = data.get('text', '')
    location = data.get('location', '')
    image_data = data.get('image', None)
    target_lang = data.get('lang', 'en')

    system_prompt = (
        "You are an AI assistant routing Indian civic complaints to the correct department. "
        f"Generate the 'complaint_letter' body strictly in this language: '{target_lang}'. "
        "Analyze the content and respond ONLY with a clean, un-markdown wrapped JSON string mapping these keys exactly:\n"
        '{"department":"Full Department Title","department_short":"Acronym","icon":"emoji","official_title":"Title",'
        '"official_name":"Indian Name","email":"dept@gov.in","phone":"1800-xx-xxxx","priority":"High/Medium/Low",'
        '"category":"Category","resolution_days":7,"tags":["tag1","tag2"],"route":["Intake","Field"],"complaint_letter":"Letter Body"}'
    )

    messages = [{"role": "system", "content": system_prompt}]
    user_message_content = []
    
    if image_data and ',' in image_data:
        user_message_content.append({"type": "text", "text": f"Analyze context. Problem: {text}. Location: {location}."})
        user_message_content.append({"type": "image_url", "image_url": {"url": image_data}})
    else:
        user_message_content.append({"type": "text", "text": f"Issue Description: {text}\nLocation Context: {location}"})
        
    messages.append({"role": "user", "content": user_message_content})

    try:
        response = client.chat.completions.create(
            model=FREE_MODEL,
            messages=messages,
            max_tokens=1200
        )
        raw_output = response.choices[0].message.content.strip()
        cleaned_json = re.sub(r'^```json\s*|\s*```$', '', raw_output, flags=re.IGNORECASE).strip()
        return jsonify(json.loads(cleaned_json))
    except Exception as e:
        return jsonify({"error": f"AI Parsing Registry Exception: {str(e)}"}), 500

@app.route('/api/analyze-cctv', methods=['POST'])
def analyze_cctv():
    data = request.json
    cam_id = data.get('camId')
    cam_name = data.get('camName')
    image_data = data.get('image')

    system_prompt = (
        "You are an AI city surveillance monitoring engine for Hyderabad, India. "
        "Analyze parameters and output cleanly structured raw JSON schema tracking situational incidents:\n"
        '{"scene_summary":"Summary description","threat_level":"CRITICAL/HIGH/MODERATE/SAFE",'
        '"alerts":[{"type":"Incident Type","severity":"critical/high/medium/low","emoji":"⚠️","title":"Title",'
        '"description":"Details","departments":["Police"],"dispatch_message":"Dispatch instructions","confidence":95}]}'
    )

    messages = [{"role": "system", "content": system_prompt}]
    user_message_content = []
    
    if image_data and ',' in image_data:
        user_message_content.append({"type": "text", "text": f"Process snapshot stream location array: {cam_id} - {cam_name}."})
        user_message_content.append({"type": "image_url", "image_url": {"url": image_data}})
    else:
        user_message_content.append({"type": "text", "text": f"Generate baseline tracking matrix simulation for {cam_id} ({cam_name})."})
        
    messages.append({"role": "user", "content": user_message_content})

    try:
        response = client.chat.completions.create(
            model=FREE_MODEL,
            messages=messages,
            max_tokens=1000
        )
        raw_output = response.choices[0].message.content.strip()
        cleaned_json = re.sub(r'^```json\s*|\s*```$', '', raw_output, flags=re.IGNORECASE).strip()
        return jsonify(json.loads(cleaned_json))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ══════════════════════════════════════════
#  ANALYTICS & DOCUMENT COMPILATION MODULES
# ══════════════════════════════════════════
@app.route('/api/analytics/metrics', methods=['GET'])
def get_analytics_metrics():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT department, COUNT(*) as total,
                       SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) as pending,
                       SUM(CASE WHEN status='Resolved' THEN 1 ELSE 0 END) as resolved
                FROM complaints GROUP BY department
            ''')
            metrics = cursor.fetchall()
        return jsonify({"success": True, "metrics": metrics})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@app.route('/api/complaints/export-pdf/<ref_id>')
def export_complaint_pdf(ref_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM complaints WHERE ref_id = %s', (ref_id,))
            c = cursor.fetchone()
        if not c:
            return "Reference identifier target matrix evaluation record missing.", 404
            
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        
        pdf.set_font("Helvetica", style="B", size=16)
        pdf.cell(200, 10, txt="GOVCONNECT OFFICIAL GRIEVANCE DOSSIER", ln=True, align="C")
        pdf.ln(10)
        
        pdf.set_font("Helvetica", size=12)
        pdf.cell(200, 10, txt=f"Grievance Reference Token ID: {c['ref_id']}", ln=True)
        pdf.cell(200, 10, txt=f"Assigned Department Vector: {c['department']}", ln=True)
        pdf.cell(200, 10, txt=f"Target Core Priority Level: {c['priority']}", ln=True)
        pdf.cell(200, 10, txt=f"Operational Processing Status Flag: {c['status']}", ln=True)
        pdf.cell(200, 10, txt=f"Registered Interface Core Coordinates: Lat {c['latitude']}, Lon {c['longitude']}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", style="B", size=12)
        pdf.cell(200, 10, txt="Auto-Generated Document Body Matrix Text:", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 8, txt=c['description'])
        
        output = io.BytesIO()
        pdf_string = pdf.output(dest='S').encode('latin-1')
        output.write(pdf_string)
        output.seek(0)
        
        return send_file(output, download_name=f"GovConnect_{ref_id}.pdf", mimetype="application/pdf")
    except Exception as e:
        return str(e), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5555)
