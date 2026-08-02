LinkedIn Agent

This project researches current Data and AI trends with Gemini Google Search grounding, writes a sourced LinkedIn post, creates one square visual, and can publish to a personal LinkedIn profile.

By default it uses `gemini-2.5-flash` for text/research and local card/diagram rendering for images. Google lists free-tier Search grounding for Gemini 2.5 Flash models, while Gemini 3.x Search grounding is tied to paid-tier search quotas.

The image path is intentionally local by default:

```yaml
visuals:
  allow_ai_illustrations: false
```

That means Gemini writes and verifies the post, while the project renders LinkedIn-ready visuals locally with Python.

## Setup

1. Install dependencies:

```bash
python3 -m pip install -e ".[dev]"
```

2. In your LinkedIn Developer app, add this authorized redirect URL exactly for local OAuth:

```text
http://127.0.0.1:8080/callback
```

If LinkedIn rejects a local HTTP redirect URL, use the Postman callback instead: `https://oauth.pstmn.io/v1/callback`.

3. Set local environment variables:

```bash
export GEMINI_API_KEY="..."
export LINKEDIN_CLIENT_ID="..."
export LINKEDIN_CLIENT_SECRET="..."
export LINKEDIN_ACCESS_TOKEN="..."
```

4. After OAuth, run `python -m linkedin_ai_agent.cli whoami` and copy `owner_urn` into `config/agent.yaml` under `linkedin.owner_urn`.

## Commands

```bash
python -m linkedin_ai_agent.cli auth-local
python -m linkedin_ai_agent.cli auth --redirect-uri "https://oauth.pstmn.io/v1/callback"
python -m linkedin_ai_agent.cli whoami
python -m linkedin_ai_agent.cli preflight
python -m linkedin_ai_agent.cli research
python -m linkedin_ai_agent.cli generate
python -m linkedin_ai_agent.cli preview
python -m linkedin_ai_agent.cli publish-preview --confirm
python -m linkedin_ai_agent.cli run --dry-run
python -m linkedin_ai_agent.cli run
python -m linkedin_ai_agent.cli token-status
```

`preview` generates and stages the exact text and image for review. `publish-preview --confirm` publishes only that staged version; it does not regenerate the content. `run --dry-run` completes research, writing, validation, and image generation without contacting LinkedIn publishing endpoints. `run` is intended for unattended automation and publishes immediately after its gates pass.

## GitHub Actions

The workflow runs at `08:00 UTC` Monday-Friday, which is `09:00 Africa/Lagos`. Store these repository secrets before enabling live scheduled posting:

- `GEMINI_API_KEY`
- `LINKEDIN_CLIENT_ID`
- `LINKEDIN_CLIENT_SECRET`
- `LINKEDIN_ACCESS_TOKEN`

Set repository variable `LINKEDIN_TOKEN_EXPIRES_AT` to the token expiry timestamp, for example `2026-09-25T09:00:00Z`, unless `.state/linkedin_token_metadata.json` already exists on the `automation-state` branch.

The workflow writes reports and non-secret publication history to an `automation-state` branch. It opens an issue when token metadata says the LinkedIn token expires within seven days.

## Safety Gates

Publishing is skipped when sources are missing, topic confidence is low, the topic was recently covered, the post contains hype or unsafe content markers, image validation fails, upload fails, or the LinkedIn token is expired.

References used for the implementation:

- [Gemini Search grounding](https://ai.google.dev/gemini-api/docs/google-search)
- [Gemini image generation](https://ai.google.dev/gemini-api/docs/image-generation)
- [LinkedIn Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-04)
- [LinkedIn Images API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api?view=li-lms-2026-05)
- [LinkedIn OAuth flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow)
