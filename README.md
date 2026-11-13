# Weather agent

An AI agent that checks the weather for my city every day and decides whether an alert is needed.

## Tools
- `get_weather`: the last 5 days of weather from Open-Meteo
- `get_history`: its own past decisions, read from my Google Sheet (its memory)
- `search_guidelines`: looks up rules in `guidelines.md` (retrieval)

## Guardrails
- Only the tools above can run. Anything else is refused.
- The agent stops after 6 steps.
- An alert needs a message and a valid source from `guidelines.md`.
- The AI recommends. My code decides.

## Tests
`python weather_log.py test` runs 5 scenarios. They run automatically on every push.

## Run it
- `python weather_log.py agent-dry` (nothing is saved)
- `python weather_log.py agent` (saves to the sheet)
