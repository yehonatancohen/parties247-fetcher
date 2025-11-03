import requests, json, datetime, time, pathlib

OUTPUT_FILE = pathlib.Path("events_nightlife.json")

def run_job():
    """Fetch Tel Aviv nightlife events."""
    url = "https://www.go-out.co/endOne/getEventsByTypeNew"
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9,he;q=0.8',
        'content-type': 'application/json',
        'origin': 'https://www.go-out.co',
        'priority': 'u=1, i',
        'referer': 'https://www.go-out.co/tickets/nightlife',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
    }
    payload = {
        "skip": 0,
        "Types": ["תל אביב", "מועדוני לילה"],
        "limit": 100,
        "recivedDate": datetime.datetime.utcnow().isoformat(),
        "location": "IL"
    }
    headers = {"Content-Type": "application/json"}

    r = requests.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()

    urls = [
        f"https://www.go-out.co/event/{item['Url']}?aff={{ref}}"
        for item in data.get("events", [])
        if "Url" in item
    ]

    add_parties_to_carousel_from_urls(urls, "חיי לילה")
    save_json(data)
    print(f"[{time.ctime()}] Saved {len(urls)} nightlife events")
    return data


def add_parties_to_carousel_from_urls(urls, carousel_name):
    """Placeholder: integrate your real carousel handler here."""
    print(f"Adding {len(urls)} parties to carousel '{carousel_name}'")


def save_json(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run_job()