import logging

import httpx
from datetime import datetime, timezone

from app.integrations.base import BaseIntegration, Capability
from app.integrations.registry import register
from app.core.security import decrypt_secret

logger = logging.getLogger("ghosttrace.integrations.github")

_EVENT_MAP = {
    "PushEvent": ("git.push", "Code push"),
    "PullRequestEvent": ("git.pr", "Pull request"),
    "PullRequestReviewEvent": ("git.pr_review", "PR review"),
    "IssuesEvent": ("git.issue", "Issue"),
    "IssueCommentEvent": ("git.issue_comment", "Issue comment"),
    "CreateEvent": ("git.create", "Branch/tag created"),
    "DeleteEvent": ("git.delete", "Branch/tag deleted"),
    "WatchEvent": ("git.star", "Starred repo"),
    "ForkEvent": ("git.fork", "Forked repo"),
    "ReleaseEvent": ("git.release", "Release published"),
    "CommitCommentEvent": ("git.commit_comment", "Commit comment"),
}


@register("github")
class GitHubIntegration(BaseIntegration):
    kind = "github"
    display_name = "GitHub Activity"

    def _cfg(self):
        return (self.integration.config if self.integration else {}) or {}

    def _username(self):
        return self._cfg().get("username") or ""

    def _token(self):
        return decrypt_secret(self._cfg().get("access_token_enc", ""))

    def _headers(self):
        h = {"Accept": "application/vnd.github+json"}
        tok = self._token()
        if tok:
            h["Authorization"] = f"Bearer {tok}"
        return h

    def capabilities(self):
        has_user = bool(self._username())
        has_token = bool(self._token())
        return [
            Capability("public_events", has_user,
                       "Public activity feed (pushes, PRs, issues, stars) via /users/{u}/events" if has_user
                       else "Set a GitHub username in the integration config.",
                       requires=["username"] if not has_user else []),
            Capability("private_events", has_token,
                       "Authenticated — private repo events included" if has_token
                       else "Add a personal access token (public events only) for private-repo visibility."),
            Capability("identity", has_token, "GitHub account identity via /user" if has_token else "Requires token"),
        ]

    async def sync(self):
        username = self._username()
        summary = {"ok": False, "events_created": 0}
        if not username:
            summary["error"] = "username not configured"
            if self.integration:
                self.integration.last_error = summary["error"]
                self.integration.status = "error"
                if self.db:
                    self.db.commit()
            return summary
        from app.services.events import ingest_event
        async with httpx.AsyncClient(timeout=30, headers=self._headers()) as client:
            # identity when token present
            if self._token():
                try:
                    r = await client.get("https://api.github.com/user")
                    if r.status_code == 200:
                        me = r.json()
                        ingest_event(
                            self.db, self.user_id, integration_kind="github", source="github",
                            application="GitHub Account", event_type="account.identity", category="account",
                            description=f"GitHub identity verified: {me.get('login')}",
                            metadata={"login": me.get("login"), "id": me.get("id"), "public_repos": me.get("public_repos")},
                            collection_method="api", permission_status="authorized", confidence=1.0,
                            dedup_key=f"github:identity:{me.get('id')}",
                        )
                        summary["events_created"] += 1
                except Exception as e:
                    summary["identity_error"] = str(e)
            # activity feed
            try:
                r = await client.get(f"https://api.github.com/users/{username}/events",
                                     params={"per_page": 100})
                if r.status_code == 200:
                    for ev in r.json():
                        etype, label = _EVENT_MAP.get(ev.get("type", ""), ("git.activity", ev.get("type", "activity")))
                        repo = (ev.get("repo") or {}).get("name")
                        payload = ev.get("payload") or {}
                        desc = f"{label} on {repo}"
                        if ev.get("type") == "PushEvent":
                            n = payload.get("size") or len(payload.get("commits", []))
                            ref = (payload.get("ref") or "").replace("refs/heads/", "")
                            desc = f"{label}: {n} commit(s) to {repo}" + (f" (branch {ref})" if ref else "")
                        ingest_event(
                            self.db, self.user_id, integration_kind="github", source="github",
                            application=repo, event_type=etype, category="work",
                            description=desc,
                            timestamp=ev.get("created_at"),
                            metadata={"github_event_id": ev.get("id"), "type": ev.get("type"),
                                      "repo": repo, "action": payload.get("action")},
                            collection_method="api", permission_status="authorized", confidence=1.0,
                            dedup_key=f"github:event:{ev.get('id')}",
                        )
                        summary["events_created"] += 1
                    summary["ok"] = True
                else:
                    summary["status"] = r.status_code
            except Exception as e:
                summary["error"] = str(e)

        if self.integration:
            self.integration.last_sync_at = datetime.now(timezone.utc)
            self.integration.status = "ok" if summary["ok"] else "error"
            self.integration.last_error = summary.get("error")
            if self.db:
                self.db.commit()
        return summary