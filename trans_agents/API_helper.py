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


def process_bus_route(route: Dict) -> Dict:
    """Process a single bus route from Google Routes API response."""
    if not route:
        return {}
    
    legs = route.get("legs", [{}])
    steps = [step for leg in legs for step in leg.get("steps", []) if step.get("travelMode") == "TRANSIT"]
    
    if not steps:
        return {}
        
    # Calculate total fare if available
    advisory = route.get("travelAdvisory", {})
    fare = advisory.get("transitFare", {})
    
    # Get origin and destination for currency detection
    origin = legs[0].get("startAddress", "") if legs and isinstance(legs, list) and len(legs) > 0 else ""
    destination = legs[-1].get("endAddress", "") if legs and isinstance(legs, list) and len(legs) > 0 else ""
    
    # Determine currency based on location
    origin_country, default_currency = _get_country_currency(origin)
    dest_country, _ = _get_country_currency(destination)
    
    # If origin and destination are in different countries, prefer the origin's currency
    fare_currency = fare.get('currencyCode', default_currency)
    
    # Extract fare amount
    fare_units = fare.get('units', 0)
    fare_nanos = fare.get('nanos', 0)
    
    # Calculate total fare in the smallest unit (e.g., paise for INR)
    try:
        total_fare = float(fare_units) + (float(fare_nanos) / 1e9)
    except (TypeError, ValueError):
        total_fare = 0.0
    
    # Format fare string with the appropriate currency symbol
    if total_fare > 0:
        if fare_currency == 'INR':
            fare_str = f"₹{total_fare:,.2f}"
        elif fare_currency == 'USD':
            fare_str = f"${total_fare:,.2f}"
        else:
            fare_str = f"{fare_currency} {total_fare:,.2f}"
    else:
        fare_str = "Fare not available"
    
    # Process segments
    segments = []
    for step in steps:
        transit = step.get("transitDetails", {})
        if not transit:
            continue
            
        departure_stop = transit.get("stopDetails", {}).get("arrivalStop", {}).get("name", "Unknown Stop")
        arrival_stop = transit.get("stopDetails", {}).get("departureStop", {}).get("name", "Unknown Stop")
        
        segments.append({
            "bus_name": transit.get("transitLine", {}).get("name", "Unknown Bus"),
            "departure_stop": departure_stop,
            "arrival_stop": arrival_stop,
            "departure_time": transit.get("departureTime", ""),
            "arrival_time": transit.get("arrivalTime", ""),
            "num_stops": transit.get("stopCount", 0),
            "headsign": transit.get("headsign", ""),
            "transit_line": transit.get("transitLine", {}).get("name", ""),
        })
    
    if not segments:
        return {}
    
    # Calculate total duration in seconds
    duration_seconds = sum(
        (datetime.fromisoformat(s["arrival_time"].replace("Z", "")) - 
         datetime.fromisoformat(s["departure_time"].replace("Z", ""))).total_seconds()
        for s in segments if s.get("departure_time") and s.get("arrival_time")
    )
    
    # Format duration as H:MM
    hours = int(duration_seconds // 3600)
    minutes = int((duration_seconds % 3600) // 60)
    duration = f"{hours}:{minutes:02d}"
    
    return {
        "segments": segments,
        "total_duration": duration,
        "total_fare": total_fare,  # Numeric value for calculations
        "fare_display": fare_str,  # Formatted string for display
        "fare_currency": fare_currency,  # Currency code
        "total_transfers": len(segments) - 1,
        "distance_km": round(route.get("distanceMeters", 0) / 1000, 1),
        "departure_time": segments[0].get("departure_time", "") if segments else "",
        "arrival_time": segments[-1].get("arrival_time", "") if segments else "",
    }


def process_train_route(route: Dict) -> Dict:
    """
    Process a single train route from Google Routes API response.
    Similar to process_bus_route but with train-specific formatting.
    """
    if not route:
        return {}
        
    # Process as bus route first to get common fields
    train_route = process_bus_route(route)
    if not train_route:
        return {}
    
    # Ensure transport_type is set to train
    train_route["transport_type"] = "train"
    
    # Update segment transport types if they exist
    if "segments" in train_route and isinstance(train_route["segments"], list):
        for segment in train_route["segments"]:
            if "bus_name" in segment:
                segment["train_name"] = segment.pop("bus_name").replace("Bus", "Train")
            segment["transport_type"] = "train"
    
    return train_route


def get_buses_from_api(origin: str, destination: str, date_time: datetime) -> dict:
    """
    Fetch bus routes between origin and destination from Google Routes API.
    Returns: Processed bus routes with only essential information
    """
    # Get API key from environment variables
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("⚠️ GOOGLE_MAPS_API_KEY not found in environment variables. Please add it to your .env file.")
    
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.duration,routes.distanceMeters,"
            "routes.legs.steps.transitDetails,"
            "routes.legs.steps.travelMode,"
            "routes.travelAdvisory.transitFare"
        )
    }
    
    payload = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": "TRANSIT",
        "transitPreferences": {
            "allowedTravelModes": ["BUS"],
            "routingPreference": "LESS_WALKING"
        },
        "departureTime": date_time.isoformat() + "Z",
        "computeAlternativeRoutes": True,
    }
    
    print(f"🚌 Fetching buses: {origin} → {destination}")
    print(f"⏰ Departure time: {date_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=(10, 30))
        response.raise_for_status()
        result = response.json()
        
        # Process routes to extract only essential information
        processed_routes = [process_bus_route(route) for route in result.get("routes", [])]
        print(f"✅ Processed {len(processed_routes)} bus routes")
        
        return {
            "origin": origin,
            "destination": destination,
            "departure_time": date_time.isoformat(),
            "transport_type": "bus",
            "routes": processed_routes
        }
        
    except requests.exceptions.Timeout:
        raise TimeoutError("⏱️ Google Routes API request timed out. The service is slow or unavailable.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            raise PermissionError("⚠️ API access denied. Check your Google API key.")
        elif e.response.status_code == 429:
            raise ConnectionError("⚠️ Rate limit exceeded. Please wait before trying again.")
        else:
            error_msg = e.response.text[:500] if hasattr(e, 'response') else str(e)
            raise ConnectionError(f"⚠️ API error: HTTP {e.response.status_code} - {error_msg}")
    except Exception as e:
        raise Exception(f"❌ Error fetching bus routes: {str(e)}")


def get_trains_from_api(origin: str, destination: str, date_time: datetime) -> dict:
    """
    Fetch train routes between origin and destination from Google Routes API.
    Returns: Processed train routes with only essential information
    """
    # Get API key from environment variables
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ValueError("⚠️ GOOGLE_MAPS_API_KEY not found in environment variables. Please add it to your .env file.")
    
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.duration,routes.distanceMeters,"
            "routes.legs.steps.transitDetails,"
            "routes.legs.steps.travelMode,"
            "routes.travelAdvisory.transitFare"
        )
    }
    
    payload = {
        "origin": {"address": origin},
        "destination": {"address": destination},
        "travelMode": "TRANSIT",
        "transitPreferences": {
            "allowedTravelModes": ["RAIL"],
            "routingPreference": "FEWER_TRANSFERS"
        },
        "departureTime": date_time.isoformat() + "Z",
        "computeAlternativeRoutes": True,
    }
    
    print(f"🚆 Fetching trains: {origin} → {destination}")
    print(f"⏰ Departure time: {date_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=(10, 30))
        response.raise_for_status()
        result = response.json()
        
        # Process routes to extract only essential information
        processed_routes = [process_train_route(route) for route in result.get("routes", [])]
        print(f"✅ Processed {len(processed_routes)} train routes")
        
        return {
            "origin": origin,
            "destination": destination,
            "departure_time": date_time.isoformat(),
            "transport_type": "train",
            "routes": [r for r in processed_routes if r]  # Filter out any empty routes
        }
        
    except requests.exceptions.Timeout:
        raise TimeoutError("⏱️ Google Routes API request timed out. The service is slow or unavailable.")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            raise PermissionError("⚠️ API access denied. Check your Google API key.")
        elif e.response.status_code == 429:
            raise ConnectionError("⚠️ Rate limit exceeded. Please wait before trying again.")
        else:
            error_msg = e.response.text[:500] if hasattr(e, 'response') else str(e)
            raise ConnectionError(f"⚠️ API error: HTTP {e.response.status_code} - {error_msg}")
    except Exception as e:
        raise Exception(f"❌ Error fetching train routes: {str(e)}")
