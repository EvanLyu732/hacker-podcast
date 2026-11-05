# Hosting and daily refresh

The site is a static site served from `dist/`. The HN snapshot is in
`dist/data.json`, with comments and episode links in `dist/details.json`.

The repository is intended for Cloudflare Pages Git integration. Connect this
repository in Cloudflare, use the default branch as the production branch,
leave the build command empty, and set the build output directory to `dist`.
Cloudflare assigns a `pages.dev` URL; a domain can be connected later after its
owner verifies the required DNS records. The Pages account is not configured by
this file.

`.github/workflows/refresh-data.yml` requests a daily refresh at 04:00 Beijing
time, and a retry at 05:30 if the successful snapshot is not from that day.
It can also be triggered manually with `workflow_dispatch`. The existing
`refresh_pipeline.py` performs a full scan in a temporary staging directory,
checks that the new data has a real current timestamp and preserves previously
verified shows, comments, episodes and Spotify links, and runs the test suite.
On failure, it does not copy the staged data or push a commit. On success, the
workflow commits only validated data outputs and pushes them to the default
branch. A concurrent source update causes the push to fail rather than overwrite
it. Cloudflare Pages Git integration is expected to deploy the new commit.
Set the GitHub Actions repository variable `PUBLIC_SITE_URL` to the public HTTPS
site origin (for example the assigned `pages.dev` address). The workflow reads
its public `data.json` until it equals the validated snapshot; without the
variable or if publication remains stale, the workflow fails visibly.
Optionally create a Cloudflare Pages deploy hook for the production branch and
store its URL in the GitHub Actions secret `CLOUDFLARE_DEPLOY_HOOK`. If the
public snapshot stays stale, the workflow calls this hook once and checks again.
Never put that URL in source control or a public log. The retry run also checks
publication if today's data was already committed.

GitHub's scheduled events can be delayed, dropped, or disabled after extended
repository inactivity, and the public upstream services can fail. The second
schedule is a retry, not a guarantee. Monitor the GitHub Actions run history
and confirm that the public site's `data.json` timestamp advances; investigate
failed or absent runs. The first manually triggered workflow and the first
automatic 04:00 run must both be verified before relying on unattended updates.
GitHub's docs: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
Cloudflare's setup guide: https://developers.cloudflare.com/pages/get-started/git-integration/
