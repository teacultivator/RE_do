import os, requests, time, re, json
from datetime import datetime, date
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv
import pandas as pd
from ast import literal_eval
from dateutil.relativedelta import relativedelta

try:
    env_path = find_dotenv()
    load_dotenv(env_path if env_path else None)
except Exception:
    pass

API_KEY = os.getenv("AMADEUS_API_KEY")
API_SECRET = os.getenv("AMADEUS_API_SECRET")

print(API_KEY, API_SECRET)

ACCESS_TOKEN = None
TOKEN_EXPIRY = 0

def get_access_token():
    global ACCESS_TOKEN, TOKEN_EXPIRY
        
    if ACCESS_TOKEN and time.time() < TOKEN_EXPIRY:
        return ACCESS_TOKEN
 
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": API_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
    try:
        if not API_KEY or not API_SECRET:
            missing = []
            if not API_KEY:
                missing.append("AMADEUS_API_KEY")
            if not API_SECRET:
                missing.append("AMADEUS_API_SECRET")
            raise Exception(f"Missing environment variables: {', '.join(missing)}. Ensure they are set in your .env or environment.")

        response = requests.post(url, data=data, headers=headers, timeout=10)
        if response.status_code != 200:
            try:
                err_body = response.json()
            except Exception:
                err_body = {"raw": response.text}
            raise Exception(f"Failed to generate access token: {response.status_code} - {err_body}")
        
        data = response.json()
        ACCESS_TOKEN = data["access_token"]
        TOKEN_EXPIRY = time.time() + int(data["expires_in"]) - 20 # 20 sec buffer
        
        return ACCESS_TOKEN
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error while getting access token: {e}")
    

def search_flights(origin_city: str, origin_country:str ,destination_city: str, destination_country:str, date: str, token: str) -> list:
    load_dotenv()

    genai.configure(api_key = os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt1 = f"""
    You are a helpful Flight Agency Assistant.
    Return only a tuple of IATA city codes. Input will be a tuple of 2 city names: (origin_city, destination_city).
    For each city name, identify the correct IATA city code. If the city has multiple airports, return the unified city code instead of individual airport codes.
    Output format must be a python tuple: (IATA_origin, IATA_destination).
    Do not add explanations, descriptions, markdown, or extra text.
    Your task: {(origin_city,origin_country, destination_city,destination_country)}
    Examples:
    """

    codes = model.generate_content(prompt1).text
    print(codes)
    codes_clean = codes.strip()
    if codes_clean.startswith("```"):
        lines = codes_clean.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            if lines[-1].startswith("```"):
                codes_clean = "\n".join(lines[1:-1]).strip()
    codes_clean = codes_clean.strip()
    tuple_pattern = r'\(["\']?([A-Z]{3})["\']?\s*,\s*["\']?([A-Z]{3})["\']?\)'
    match = re.search(tuple_pattern, codes_clean)
    if match:
        codes_clean = f"('{match.group(1)}', '{match.group(2)}')"
    
    try:
        codes = literal_eval(codes_clean)
        if not isinstance(codes, (tuple, list)) or len(codes) != 2:
            raise ValueError(f"Expected a tuple of 2 codes, got: {codes}")
        # Ensure codes are strings
        codes = tuple(str(code).strip() for code in codes)
    except (ValueError, SyntaxError) as e:
        raise Exception(f"Failed to parse IATA codes from LLM response: {str(e)}. Raw response: {repr(codes)}")

    try:
        params = {
            "originLocationCode": codes[0],
            "destinationLocationCode": codes[1],
            "departureDate": date,
            "adults": 1
        }
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        
        print("Parameters before API call:",params,sep='\n')
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, params=params, headers=headers, timeout=90)


        result = response.json()
        print("Number of flight offers returned by Amadeus:", len(result["data"]), end="\n\n")

        if response.status_code != 200:
            error_msg = "Unknown API error"
            if "errors" in result and result["errors"]:
                error = result["errors"][0]
                error_msg = f"{error.get('title', '')}: {error.get('detail', '')}"
            
            return []
    
        return result["data"]
        
    except Exception as e:
        print(f"An exception occured during/after the API call: {str(e)}")
        return []