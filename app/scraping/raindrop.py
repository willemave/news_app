import requests
import datetime
from app.config import settings

def fetch_new_raindrops(last_run_date: datetime.datetime):
    """
    Fetch new links from Raindrop.io since 'last_run_date'.
    This function returns a list of dictionaries or objects with 'url' etc.
    """
    # Ensure last_run_date is timezone-aware
    if last_run_date.tzinfo is None:
        last_run_date = last_run_date.replace(tzinfo=datetime.timezone.utc)

    token = settings.RAINDROP_TOKEN
    if not token:
        print("Raindrop token not configured.")
        return []

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        response = requests.get(
            "https://api.raindrop.io/rest/v1/raindrops/0",
            headers=headers
        )
        response.raise_for_status()
        
        data = response.json()
        raindrops = []
        
        for item in data.get("items", []):
            created = datetime.datetime.fromisoformat(item["created"].replace("Z", "+00:00"))
            if created > last_run_date:
                raindrops.append({
                    "url": item["link"],
                    "title": item.get("title"),
                    "created": created
                })
        
        return raindrops
        
    except requests.RequestException as e:
        print(f"Error fetching raindrops: {e}")
        return []
