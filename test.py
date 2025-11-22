import os, requests
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("AMADEUS_API_KEY")
SECRET = os.getenv("AMADEUS_API_SECRET")
print("KEY:", KEY)
print("SECRET:", SECRET)

resp = requests.post(
    "https://test.api.amadeus.com/v1/security/oauth2/token",
    data={
        "grant_type": "client_credentials",
        "client_id": KEY,
        "client_secret": SECRET,
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
print(resp.status_code, resp.text)