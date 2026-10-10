# EduRadar Copilot add-on

Adds `/api/copilot/ask` and React `/copilot` tab.

The default setup uses SQLite for factual student queries and TF-IDF retrieval from `knowledge/demo_support_guidelines.md` for document questions. Optional server-side OpenAI Chat Completions can turn retrieved guideline excerpts into concise grounded prose. **Student data is never sent to an external LLM by this add-on.**

## Local run

- Set environment variable `EDURADAR_COPILOT_ENABLED=1`
- Keep `EDURADAR_COPILOT_DEMO_ONLY=1` (default)
- Run your existing FastAPI server; rebuild React using `cd frontend && npm ci && npm run build`
- Open `/copilot`.

## Railway

- Push these updates to GitHub; Railway redeploys with the existing Dockerfile.
- In service Variables add `EDURADAR_COPILOT_ENABLED=1` and `EDURADAR_COPILOT_DEMO_ONLY=1`.
- Keep your existing `EDURADAR_DB` persistent-volume settings.
- Optional: add `OPENAI_API_KEY` as a Railway secret and `EDURADAR_COPILOT_USE_LLM=1`. This incurs API charges. Keep the key **only** in the Railway backend variables; never expose it with a `VITE_` prefix.
- Keep your site limited to fictional data until proper login, permissions, rate limits and audit logs exist. Current site has no authentication. Do not set demo-only to 0 on a public deployment without securing the API.

## Supported queries

- Which students have declining attendance?
- Which high priority students are unreviewed?
- What follow-ups are due tomorrow? (uses server date)
- What interventions are overdue?
- Show student S00047.
- How should teachers handle missing assignments?
- Why should teachers avoid reacting to one poor test?

### Notes

- This is an initial limited-intent retrieval-grounded copilot, not unrestricted natural-language SQL. It responds to supported patterns and uses retrieved demo guidelines for other questions. Add a robust intent router and policy authentication before production.
- Student searches show a max of 20 rows. Followups also show 20.
- When the optional LLM is enabled, only demo guideline sections and the user question go to the provider. Teachers must not put private student data into free-text prompts.
