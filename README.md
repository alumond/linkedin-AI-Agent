# LinkedIn Studio

A local review desk for Almond's LinkedIn publisher. Posts alternate between inspected public GitHub builds and freshly researched data, AI, analytics and business developments, with a fresh Codex-generated image and **your approval before every publication**.

## Review on this device

Double-click `Start LinkedIn Studio.command`, or run:

```bash
PYTHONPATH=.vendor:src python3 -m linkedin_ai_agent.review_server
```

Open **http://127.0.0.1:8765**. The server binds only to this device. It uses your existing GitHub CLI sign-in; LinkedIn and Gemini credentials stay in GitHub Actions secrets.

The desk shows the exact pending post, its image, source links, checks and recent publication history. **Approve for schedule** approves only that version of the text and image. Any change requires approval again. **Request changes** revokes approval and starts draft revision; Codex then needs to generate/review the revised image. Approval never publishes immediately.

Approved posts publish at **09:17 Africa/Lagos, weekdays**, through GitHub Actions. Your browser and local server need not remain open after approval. The device and Codex must be running for the separate local Codex image task. Without approval, the ready post remains available for review.

A desktop popup appears when both the draft and image are ready. **Review post** opens the desk; **Later** dismisses it. A new version triggers a new popup, with at most one reminder per version per day. The local service starts at login and runs from `~/Library/Application Support/Almond LinkedIn Studio`. It must be running for popups. After updating the project, run `python3 scripts/install_review_service.py` to update this installed copy. To stop it, run `launchctl bootout gui/$(id -u)/com.almond.linkedin-review`; remove `~/Library/LaunchAgents/com.almond.linkedin-review.plist` to disable login startup.

## Content and originality

- Alternate portfolio stories with evidence-backed developments across the configured editorial topics. If one source route fails, try the other without recycling old content.
- Discover public, non-fork projects under `alumond`, prioritizing the configured personal builds and rotating projects before revisiting them.
- Read repository documentation, selected code and recent commits. Write about actual features, design choices, problems solved and honest limitations. Do not invent deployments, users, results or experiments.
- Exclude **Stanforteedge and HR dashboards/HR analytics**, including matching repository descriptions, filenames and source content.
- Compare topics and substantial body overlap against **all available publication history**, including legacy reports. No 45-day expiry and no exhausted-library fallback.
- Reject identical image bytes and very similar visual fingerprints. Codex also compares earlier artwork for repeated composition and checks readability, relevance and factual claims.
- No sketches, model drawings, wireframes, generic AI artwork, cropped titles or internal drafting notes. Codex generates the image; Gemini supplies text only.

Historical checks cover the publisher's recorded posts, not an exhaustive export of every post ever made manually on LinkedIn. Human review remains the final check for those earlier posts and visual taste.

## Pipeline

**Verified sources → exact draft → Codex image → visual review → your approval → scheduled publication.**

`automation-state` stores the pending draft, publication history, approval, review feedback and publication journal. Main stores the code and reviewed image assets. The queue preserves a draft while its image or approval is pending. The publisher has a daily publication limit and does not automatically retry an uncertain LinkedIn create-post request.

Prepare a draft without publishing:

```bash
gh workflow run weekday-linkedin-post.yml -f mode=prepare -f dry_run=true
```

Verify the exact pending draft/image without publishing:

```bash
gh workflow run weekday-linkedin-post.yml -f mode=publish -f dry_run=true
```

A successful dry run is **not approval**. Legacy direct-publication commands cannot bypass the configured review requirement.

## Codex image task

The task prompt is ready in [docs/codex-image-task.md](docs/codex-image-task.md). **Task activation is still required in Codex.** This repository cannot invoke the conversation's imagegen tool from GitHub Actions. `pending_image` does not mean image generation has started.

A generated PNG must have a sibling JSON with: `provider: "codex_imagegen"`, `review_status: "passed"`, `topic`, `draft_sha256`, `asset_sha256`, the actual generation `prompt`, `reviewed_at`, meaningful `review_notes`, and accurate `alt_text`. Use `codex_visuals.draft_sha256` for the exact draft fingerprint and SHA-256 for the image bytes. Create the record only after inspecting the image. It documents a visual review; it does not itself detect image quality.

## Setup and maintenance

Install with `python3 -m pip install -e ".[dev]"` and authenticate `gh` for `alumond/linkedin-AI-Agent`. This device also has a bundled CLI in `.tools/gh_2.94.0_macOS_arm64/bin/gh`, used automatically if `gh` is not on PATH.

GitHub Actions secrets: `GEMINI_API_KEY`, `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `LINKEDIN_ACCESS_TOKEN`. Store token expiry in `LINKEDIN_TOKEN_EXPIRES_AT` or `.state/linkedin_token_metadata.json` on `automation-state`. Renewal reminders use the existing GitHub issue workflow.

To renew LinkedIn access, keep the developer app callback `http://127.0.0.1:8080/callback` registered, then run:

```bash
PYTHONPATH=.vendor:src python3 -m linkedin_ai_agent.token_renewal --client-id YOUR_EXISTING_CLIENT_ID
```

Open `http://127.0.0.1:8080`, enter the app's existing client secret, and follow **Authorize on LinkedIn**. The helper checks the account, existing permissions and expiry before updating `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_TOKEN_EXPIRES_AT` and the non-secret metadata on `automation-state`. Credentials stay in memory and go directly to the existing GitHub secret; they are never printed or written locally. If saving fails, use **Retry save** while the helper is running. It closes after success or 30 minutes. Renewal does not publish a post. Never commit tokens or expose them in reports.

Run checks with `PYTHONPATH=.vendor:src python3 -m pytest -q` on this device, or `pytest -q` after installing the development dependencies. Run `python -m linkedin_ai_agent.cli show-config` to inspect non-secret settings.

[Retail Revenue & Operations Command Center](projects/retail-revenue-command-center) remains a standalone portfolio project.
