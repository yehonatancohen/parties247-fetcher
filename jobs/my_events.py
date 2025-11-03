import requests, json, datetime, pathlib, time, os, stat

PAYLOAD_DIR = "auth_payload/"
TOKEN_FILE = pathlib.Path(PAYLOAD_DIR + "token.txt")
COOKIES_FILE = pathlib.Path(PAYLOAD_DIR + "cookies.json")
OUTPUT_FILE = pathlib.Path("events.json")
LOGIN_URL = "https://api.fe.prod.go-out.co/auth/login"

def _get_env_creds():
    email = os.environ.get("GOOUT_EMAIL")
    password = os.environ.get("GOOUT_PASSWORD")
    if not email or not password:
        raise RuntimeError("Set GOOUT_EMAIL and GOOUT_PASSWORD in the environment.")
    return email, password

def load_token():
    return TOKEN_FILE.read_text().strip()

def load_cookies():
    with COOKIES_FILE.open() as f:
        return json.load(f)

def fetch_events():
    headers = {
        "Authorization": f"Bearer {load_token()}",
        "Accept": "application/json",
        "Origin": "https://www.go-out.co"
    }
    params = {
        "skip": 0,
        "limit": 100,
        "filter": '{"Title":"","activeEvents":true}',
        "currentDate": datetime.datetime.utcnow().isoformat()
    }
    r = requests.get("https://api.fe.prod.go-out.co/events/myEvents",
                     headers=headers, cookies=load_cookies(), params=params)
    if (r.status_code == 401):
        renew_token_from_env()
        r = requests.get("https://api.fe.prod.go-out.co/events/myEvents",
                     headers=headers, cookies=load_cookies(), params=params)
    r.raise_for_status()
    return r.json()

def renew_token_from_env():
    email, password = _get_env_creds()
    payload = {"username": email, "password": password}
    r = requests.post(LOGIN_URL, json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Login failed: {r.status_code} {r.text}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        raise RuntimeError(f"No token in response: {json.dumps(data)[:200]}")
    TOKEN_FILE.write_text(token, encoding="utf-8")
    try:
        TOKEN_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except Exception:
        pass
    print(f"[{time.ctime()}] Token renewed.")
    return token

def save_events(data):
    json.dump(data, open(OUTPUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def run_job():
    data = fetch_events()
    print(f"[{datetime.datetime.now()}] Updated {len(data.get('events', []))} events")
    return data