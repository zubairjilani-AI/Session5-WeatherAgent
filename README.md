import os
import sys
import json
import requests
from time import sleep

# Settings
CITY = "Karachi"
CITIES = {
    "Lahore": (31.52, 74.32),
    "Karachi": (24.86, 67.01),
    "Islamabad": (33.69, 73.05),
}
GROQ_URL = "https://groq.com"
MODEL = "llama-3.1-8b-instant"

# Global Environment Variables
os.environ["GROQ_API_KEY"] = "gsk_hcucpija4asOfL3fXpv4WGdyb3FYbWFLM2ZsDczN5HZyVXVMMbp"
os.environ["SHEET_URL"] = "https://google.com"

# 1. Get weather data
def get_weather(city):
    lat, lon = CITIES[city]
    url = (
        "https://open-meteo.com"
        f"?latitude={lat}&longitude={lon}"
        "&daily=temperature_2m_max,temperature_2m_min,wind_speed_10m_max"
        "&timezone=auto&past_days=5&forecast_days=1"
    )
    d = requests.get(url, timeout=30).json()["daily"]
    days = []
    for i in range(5):
        days.append({
            "date": d["time"][i],
            "high": d["temperature_2m_max"][i],
            "low": d["temperature_2m_min"][i],
            "wind": d["wind_speed_10m_max"][i],
        })
    return {
        "city": city,
        "days": days,
        "avg_high": round(sum(x["high"] for x in days) / 5, 1),
        "avg_low": round(sum(x["low"] for x in days) / 5, 1),
        "peak_wind": max(x["wind"] for x in days),
    }

# 2. Talk to the AI
def ask_groq(messages, **extra):
    r = requests.post(
        GROQ_URL,
        headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]},
        json={"model": MODEL, "messages": messages, **extra},
        timeout=60,
    )
    if r.status_code != 200:
        raise SystemExit("Groq error: " + r.text)
    return r.json()["choices"][0]["message"]

# 3. The weather agent tools
def tool_get_weather(city):
    if city not in CITIES:
        return {"error": "city not allowed"}
    data = get_weather(city)
    summary = {k: v for k, v in data.items() if k != "days"}
    summary["daily_highs"] = [x["high"] for x in data["days"]]
    return summary

def tool_get_history(n=5):
    r = requests.get(os.environ["SHEET_URL"], params={"action": "history", "n": n}, timeout=30)
    try:
        return r.json()
    except ValueError:
        return {"error": "could not read history: " + r.text[:100]}

REAL_TOOLS = {"get_weather": tool_get_weather, "get_history": tool_get_history}

AGENT_TOOLS = [
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "Get the last 5 days of weather for a city: average high, average low, peak wind and the daily highs",
        "parameters": {"type": "object",
                       "properties": {"city": {"type": "string", "enum": list(CITIES)}},
                       "required": ["city"]}}},
    {"type": "function", "function": {
        "name": "get_history",
        "description": "Get your own most recent decisions from previous runs: time, city, advice, whether an alert was sent, and the alert message",
        "parameters": {"type": "object",
                       "properties": {"n": {"type": "integer", "description": "how many past runs, 1 to 10"}}}}},
]

def parse_decision(text):
    text = (text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        d = json.loads(text)
    except json.JSONDecodeError:
        return None
    ok = (isinstance(d, dict) and isinstance(d.get("advice"), str) and isinstance(d.get("reasoning"), str)
          and isinstance(d.get("send_alert"), bool) and isinstance(d.get("alert_message"), str))
    return d if ok else None

def apply_guardrails(d):
    message = d["alert_message"].strip()[:300]            
    send = d["send_alert"] is True and message != ""      
    return {"advice": d["advice"].strip(), "reasoning": d["reasoning"].strip(),
            "send_alert": send, "alert_message": message if send else ""}

def run_weather_agent(tools=REAL_TOOLS, max_steps=6):
    system = (
        f"You are a weather agent for {CITY}. Use your tools to check the weather and your own recent decisions. "
        "Compare today with the recent days and with your past alerts. "
        "Send an alert only if something unusual or dangerous needs attention, such as extreme heat, "
        "strong wind or a big change, and only if the history does not show you already alerted about the same thing. "
        "Never invent numbers. If a tool returns an error, do not guess: say the data is unavailable and do not alert. "
        "When you are done, reply with JSON only, with exactly these keys: "
        "advice (one or two sentences for a general reader), "
        "reasoning (two or three sentences explaining your decision with numbers), "
        "send_alert (true or false), "
        "alert_message (a short message, or an empty string if there is no alert)."
    )
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": f"Check the weather for {CITY} and decide what to do."}]
    used = []
    for step in range(1, max_steps + 1):
        msg = ask_groq(messages, tools=AGENT_TOOLS, temperature=0.2)
        calls = msg.get("tool_calls")
        if not calls:
            decision = parse_decision(msg.get("content"))
            if decision:
                return decision, used
            messages.append({"role": "assistant", "content": msg.get("content") or ""})
            messages.append({"role": "user", "content": "Reply with the JSON object only, with the 4 keys."})
            continue
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"]["arguments"] or "{}")
            print("STEP", step, "->", name, args)
            fn = tools.get(name)
            if fn is None:
                result = {"error": "tool not allowed"}
            else:
                try:
                    result = fn(**args)
                except TypeError:
                    result = {"error": "bad arguments"}
            used.append(name)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    raise SystemExit("The agent did not finish in time")

def run_agent_job(dry=False):
    decision, used = run_weather_agent()
    decision = apply_guardrails(decision)
    print("\nADVICE:", decision["advice"])
    print("REASONING:", decision["reasoning"])
    print("ALERT:", decision["send_alert"], decision["alert_message"])

    payload = {"type": "agent", "city": CITY, "tools_used": ", ".join(used), **decision}
    if dry:
        print("\nDry run. Nothing was sent to the sheet or email.")
        return
    response = requests.post(os.environ["SHEET_URL"], json=payload, timeout=30)
    print(response.status_code, response.text)
    if response.text != "OK":
        raise SystemExit("The sheet script said: " + response.text)

# Start here
if __name__ == "__main__":
    run_agent_job()
