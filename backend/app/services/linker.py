"""
Links GitHub events (PRs, commits) to Jira issues.
Strategy:
  1. Regex extraction of Jira key (e.g. PROJ-123) from text fields
  2. Heuristic fuzzy matching on PR title vs issue summary (fallback)
"""
import re
from typing import Optional


# Matches patterns like ABC-123, DEVOPS-999, PROJ-1
JIRA_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b")


def extract_jira_key(text: str) -> Optional[str]:
    """Extract first Jira issue key from text."""
    if not text:
        return None
    match = JIRA_KEY_PATTERN.search(text)
    return match.group(1) if match else None


def extract_jira_keys(text: str) -> list[str]:
    """Extract all Jira issue keys from text."""
    if not text:
        return []
    return list(dict.fromkeys(JIRA_KEY_PATTERN.findall(text)))


def link_pr_to_jira(
    pr_title: str,
    pr_body: str | None,
    branch_name: str | None,
) -> Optional[str]:
    """
    Try to find a Jira key linked to a pull request.
    Checks title → branch → body in priority order.
    """
    for source in [pr_title, branch_name, pr_body]:
        key = extract_jira_key(source or "")
        if key:
            return key
    return None


def link_commit_to_jira(commit_message: str) -> Optional[str]:
    """Extract Jira key from commit message."""
    return extract_jira_key(commit_message)


def normalize_branch_name(branch: str) -> str:
    """Extract readable part from branch names like feature/PROJ-123-add-login"""
    parts = branch.replace("/", "-").split("-")
    return " ".join(parts)
