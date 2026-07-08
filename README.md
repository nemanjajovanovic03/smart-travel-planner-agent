# Smart Travel Planner Agent

Smart Travel Planner Agent je Python/LangChain AI agent povezan sa temom TripPlanner aplikacije. Agent koristi OpenAI API za razumevanje korisnickog zahteva i generisanje plana putovanja, a OpenWeather API kao jedini eksterni izvor podataka u ovoj verziji.

## Funkcionalnosti

- CLI unos destinacije, datuma, broja putnika, budzeta i interesovanja.
- Ucitavanje zahteva iz JSON fajla.
- OpenWeather alat za vremenske napomene.
- LangChain agent koji koristi OpenAI model i alate.
- Strukturisan izlaz u JSON i Markdown formatu.
- `--mock` rezim za lokalnu demonstraciju bez OpenAI poziva.

## Struktura

```text
smart-travel-planner-agent/
  main.py
  requirements.txt
  .env.example
  examples/rome_request.json
  smart_travel_planner_agent/
    agent.py
    cli.py
    config.py
    data_loader.py
    models.py
    output_writer.py
    prompts.py
    tools.py
    weather_client.py
```

## Instalacija

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Napravi `.env` na osnovu `.env.example`:

```env
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
WEATHER_API_KEY=your_openweather_api_key
WEATHER_API_URL=https://api.openweathermap.org
```

## Pokretanje

Offline demo bez OpenAI poziva:

```bash
python main.py --input examples/rome_request.json --mock --format both --output outputs/rome_plan
```

Pravi OpenAI/LangChain agent:

```bash
python main.py --input examples/rome_request.json --format both --output outputs/rome_plan
```

Direktan CLI unos:

```bash
python main.py --destination Rome --start-date 2026-08-10 --end-date 2026-08-14 --travelers 2 --budget 800 --interests history museums food --origin Belgrade --format both --output outputs/rome_plan
```

## Ocekivani izlaz

Agent cuva:

- `outputs/rome_plan.json`
- `outputs/rome_plan.md`

JSON izlaz sadrzi:

```json
{
  "destination": "Rome",
  "period": "2026-08-10 to 2026-08-14",
  "travelers": 2,
  "summary": "...",
  "transport_suggestion": "...",
  "weather_notes": [],
  "daily_plan": [],
  "estimated_costs": {},
  "risks": [],
  "recommendations": [],
  "data_sources": []
}
```

## Veza sa zahtevima zadatka 3

- LLM model: OpenAI preko `langchain-openai`.
- Modularna struktura: CLI, agent, modeli, data loader, OpenWeather, output writer.
- Eksterni podaci: OpenWeather API.
- Prompt engineering: sistemski prompt u `prompts.py` kontrolise ulogu, zadatak i format.
- Korisnicki unos: CLI argumenti ili JSON fajl.
- Strukturisan izlaz: Markdown i JSON.
- `.env`: svi kljucevi idu u environment varijable.
- Error handling: validacija ulaza, nedostajuci API kljucevi, API greske i nevalidan LLM JSON.

## Napomena o opsegu

Ova verzija ne koristi servise za rezervacije ili pretragu prevoza. Agent pravi itinerer, vremenske napomene, rizike, preporuke i okvirnu procenu troskova na osnovu korisnickog zahteva i OpenWeather podataka.
