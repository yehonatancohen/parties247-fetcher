import requests, json, datetime, time, pathlib

OUTPUT_FILE = pathlib.Path("events_weekend.json")

def run_job():
    """Fetch weekend events."""
    now = datetime.datetime.utcnow().isoformat() + "Z"  # proper ISO format
    url = (
        f"https://www.go-out.co/endOne/getWeekendEvents"
        f"?limit=100&skip=0&recivedDate={now}&location=IL"
    )

    headers = {
        "accept": "application/json",
        "cache-control": "no-cache",
        "origin": "https://www.go-out.co",
        "referer": "https://www.go-out.co/"
    }

    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[{time.ctime()}] Saved {len(data.get('events', []))} weekend events")
    return data


def save_json(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run_job()