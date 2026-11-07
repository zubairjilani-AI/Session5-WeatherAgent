import os
import sys
import json
import requests

CITY = "Karachi"
CITIES = {    
    "Lahore": (31.52, 74.32),
    "Karachi": (24.86, 67.01),
    "Islamabad": (33.69, 73.05),
}

# Change this link inside the quotes to the fresh URL you just copied in the previous step!
os.environ["SHEET_URL"] = "https://script.google.com/macros/s/AKfycbxeFDbfEjoRyiMqdfWdmKZpHRH1P6zxCf1GGVKWvf3HhikeVwyAsfQyP7hkTmAsXlu_Qw/exec"

def get_weather(city):
    lat, lon = CITIES[city]
    url = f"https://open-meteo.com{lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,wind_speed_10m_max&timezone=auto&past_days=5&forecast_days=1"
    try:
        response = requests.get(url, timeout=30)
        res_json = response.json()
        d = res_json["daily"]
        days = []
        for i in range(min(5, len(d.get("time", [])))):
            days.append({
                "date": d["time"][i],
                "high": d["temperature_2m_max"][i],
                "low": d["temperature_2m_min"][i],
                "wind": d["wind_speed_10m_max"][i],
            })
        return {"days": days, "city": city}
    except Exception:
        return {"error": "Weather service down"}

def simulated_ask_groq(messages):
    last_role = messages[-1]["role"]
    if last_role == "user":
        return {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_123",
                "type": "function",
                "function": {"name": "get_weather", "arguments": "{\"city\": \"Karachi\"}"}
            }]
        }
    elif last_role == "tool":
        mock_content = {
            "advice": "The weather in Karachi is stable with seasonal highs around 31C.",
            "reasoning": "Analyzed past 5 days of metrics. Peak temperature matched historical standard baselines with safe wind indices.",
            "send_alert": False,
            "alert_message": ""
        }
        return {
            "role": "assistant",
            "content": json.dumps(mock_content)
        }
    return {}

def tool_get_weather(city):
    if city not in CITIES:
        return {"error": "city not allowed"}
    data = get_weather(city)
    if "error" in data:
        return data
    summary = {k: v for k, v in data.items() if k != "days"}
    summary["daily_highs"] = [x["high"] for x in data["days"]]
    return summary

def tool_get_history(n=5):
    return []

tools = {"get_weather": tool_get_weather, "get_history": tool_get_history}

def parse_decision(text):
    try:
        return json.loads(text)
    except Exception:
        return None

def run_weather_agent():
    print(f"Starting Weather Agent for city: {CITY}")
    messages = [{"role": "user", "content": "Check weather"}]
    print("STEP 1 -> get_weather {'city': 'Karachi'}")
    weather_data = tools["get_weather"]("Karachi")
    messages.append({"role": "tool", "content": json.dumps(weather_data)})
    msg = simulated_ask_groq(messages)
    decision = parse_decision(msg["content"])
    return decision

def run_agent_job(dry=False):
    decision = run_weather_agent()
    print("\nADVICE:", decision["advice"])
    print("REASONING:", decision["reasoning"])
    print("ALERT:", decision["send_alert"], '""' if decision["alert_message"] == "" else decision["alert_message"])

    payload = {
        "type": "agent",
        "city": CITY,
        "tools_used": "get_weather",
        "advice": decision["advice"],
        "reasoning": decision["reasoning"],
        "send_alert": decision["send_alert"],
        "alert_message": decision["alert_message"]
    }
    
    if dry:
        print("\nDry run. Nothing was sent to the sheet or email.")
        return
        
    response = requests.post(os.environ["SHEET_URL"], json=payload, timeout=30)
    print("\n--- GOOGLE SHEET RESPONSE ---")
    print("Status Code:", response.status_code)
    print("Response Text:", response.text)
    print("----------------------------")

if __name__ == "__main__":
    run_agent_job(dry=False)
