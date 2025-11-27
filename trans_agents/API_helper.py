import os, requests, time, re, json
from datetime import datetime, date
from typing import Dict
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

# print(API_KEY, API_SECRET)

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
    # print(codes)
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
        
        # print("Parameters before API call:",params,sep='\n')
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, params=params, headers=headers, timeout=90)


        result = response.json()
        #print("Number of flight offers returned by Amadeus:", len(result["data"]), end="\n\n")

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

def _parse_routes_response(response: dict) -> list:
    """
    Parses the raw Google Routes API response into a simplified structure.
    """
    parsed_routes = []
    
    if not response or "routes" not in response:
        return parsed_routes

    for route in response["routes"]:
        route_info = {
            "total_duration": route.get("duration"),
            "total_distance_meters": route.get("distanceMeters"),
            "fare": route.get("travelAdvisory", {}).get("transitFare", {}),
            "steps": []
        }
        
        for leg in route.get("legs", []):
            for step in leg.get("steps", []):
                transit_details = step.get("transitDetails")
                if transit_details:
                    stop_details = transit_details.get("stopDetails", {})
                    transit_line = transit_details.get("transitLine", {})
                    vehicle = transit_line.get("vehicle", {})
                    
                    step_info = {
                        "departure_stop": stop_details.get("departureStop", {}).get("name"),
                        "arrival_stop": stop_details.get("arrivalStop", {}).get("name"),
                        "departure_time": stop_details.get("departureTime"),
                        "arrival_time": stop_details.get("arrivalTime"),
                        "agency_name": transit_line.get("agencies", [{}])[0].get("name"),
                        "line_name": transit_line.get("name"),
                        "vehicle_type": vehicle.get("name", {}).get("text"),
                        "num_stops": transit_details.get("stopCount"),
                        "headsign": transit_details.get("headsign")
                    }
                    route_info["steps"].append(step_info)
        
        parsed_routes.append(route_info)
        
    return parsed_routes

def get_buses_from_api(origin: str, destination: str, date_time: datetime) -> list:

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
    
    # print(f"🚌 Fetching buses: {origin} → {destination}")
    # print(f"⏰ Departure time: {date_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=(10, 30))
        response.raise_for_status()
        result = response.json()
        
        return _parse_routes_response(result)
        
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


def get_trains_from_api(origin: str, destination: str, date_time: datetime) -> list:
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
    
    # print(f"🚆 Fetching trains: {origin} → {destination}")
    # print(f"⏰ Departure time: {date_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=(10, 30))
        response.raise_for_status()
        result = response.json()
        
        return _parse_routes_response(result)
        
        
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


def simplify_flight_data(flight_offers: list) -> list:
    """
    Simplifies the raw Amadeus flight offers into a cleaner format for the LLM.
    Extracts only essential details: price, duration, and segment info.
    """
    simplified = []
    
    for offer in flight_offers:
        try:
            # Extract price
            price = offer.get("price", {})
            total_price = f"{price.get('total', 'N/A')} {price.get('currency', '')}"
            
            # Extract itineraries
            itineraries = []
            for itinerary in offer.get("itineraries", []):
                segments = []
                for segment in itinerary.get("segments", []):
                    seg_info = {
                        "departure": {
                            "iata": segment.get("departure", {}).get("iataCode"),
                            "time": segment.get("departure", {}).get("at")
                        },
                        "arrival": {
                            "iata": segment.get("arrival", {}).get("iataCode"),
                            "time": segment.get("arrival", {}).get("at")
                        },
                        "carrier": segment.get("carrierCode"),
                        "flight_number": segment.get("number"),
                        "duration": segment.get("duration")
                    }
                    segments.append(seg_info)
                
                itineraries.append({
                    "duration": itinerary.get("duration"),
                    "segments": segments
                })
            
            simplified.append({
                "id": offer.get("id"),
                "price": total_price,
                "itineraries": itineraries,
                "seats_available": offer.get("numberOfBookableSeats")
            })
            
        except Exception as e:
            print(f"Error simplifying flight offer {offer.get('id', 'unknown')}: {e}")
            continue
            
    return simplified
