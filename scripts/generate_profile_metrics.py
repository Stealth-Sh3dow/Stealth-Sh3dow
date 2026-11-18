#!/usr/bin/env python3
"""SH3DOW profile metrics: aggregate public/private GitHub data, never repo names.

Uses only Python's standard library. The PAT remains a GitHub Actions secret.
The generated SVGs contain aggregate numbers and language names, not repo details.
"""
import collections
import datetime as dt
import html
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
LOGIN = "Stealth-Sh3dow"
TOKEN = os.environ.get("GITHUB_API_TOKEN", "").strip()
OUTPUT = Path("assets")
BG = "#07101B"
CYAN = "#30E4F3"
PINK = "#FF365E"
WHITE = "#E8F7FF"
DIM = "#8CA6BA"
BAR = "#1A3043"
PALETTE = [CYAN, PINK, "#B59AFF", "#FFD66E", "#4DDBBD", "#7BA8FF", "#E0A9FF", "#FF995D"]

def gh_request(path, body=None):
    if not TOKEN:
        raise RuntimeError("README_STATS_PAT is missing; complete-account scan is disabled.")
    url = API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url, data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + TOKEN,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "sh3dow-profile-metrics",
            **({"Content-Type": "application/json"} if data is not None else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Never print endpoint URLs: a private repository name could be in one.
        raise RuntimeError("GitHub API request failed (HTTP %s)." % exc.code) from None

def graphql(query, variables=None):
    payload = gh_request("/graphql", {"query": query, "variables": variables or {}})
    if payload.get("errors"):
        reasons = ", ".join(str(error.get("type", "GraphQL error")) for error in payload["errors"])
        raise RuntimeError("Contribution query failed: " + reasons)
    return payload["data"]

def collect_repositories():
    seen = {}
    for page in range(1, 21):
        params = urllib.parse.urlencode({
            "affiliation": "owner,collaborator,organization_member",
            "visibility": "all",
            "per_page": 100,
            "page": page,
        })
        repos = gh_request("/user/repos?" + params)
        if not isinstance(repos, list):
            raise RuntimeError("Unexpected repository API response")
        for repo in repos:
            seen[repo["id"]] = repo
        if len(repos) < 100:
            return list(seen.values())
    raise RuntimeError("Too many accessible repositories: pagination limit reached.")

def collect_contributions():
    viewer = graphql("query { viewer { login createdAt } }")["viewer"]
    if viewer["login"].lower() != LOGIN.lower():
        raise RuntimeError("Personal token belongs to a different GitHub account.")
    start_year = int(viewer["createdAt"][:4])
    now = dt.datetime.now(dt.timezone.utc)
    calendar_total = 0
    annual = {}
    q = """query($from: DateTime!, $to: DateTime!) {
      viewer {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar { totalContributions }
        }
      }
    }"""
    for year in range(start_year, now.year + 1):
        first = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
        last = min(
            dt.datetime(year + 1, 1, 1, tzinfo=dt.timezone.utc) - dt.timedelta(seconds=1),
            now,
        )
        variables = {"from": first.isoformat().replace("+00:00", "Z"),
                     "to": last.isoformat().replace("+00:00", "Z")}
        data = graphql(q, variables)
        count = int(data["viewer"]["contributionsCollection"]["contributionCalendar"]["totalContributions"])
        annual[year] = count
        calendar_total += count
    return start_year, calendar_total, annual

def xml(value):
    return html.escape(str(value), quote=True)

def write_svg(name, content):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / name).write_text(content, encoding="utf-8")

def account_card(repos, start_year, contributions, annual, languages_count):
    year_now = dt.datetime.now(dt.timezone.utc).year
    entries = [
        ("PROJECTS TRACKED", f"{len(repos):,}", CYAN),
        ("TOTAL CONTRIBUTIONS", f"{contributions:,}", "#B59AFF"),
        (f"CONTRIBS IN {year_now}", f"{annual.get(year_now, 0):,}", PINK),
        ("LANGUAGES DETECTED", str(languages_count), WHITE),
    ]
    width = 940
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="190" viewBox="0 0 {width} 190" role="img">',
        '<rect width="940" height="190" rx="12" fill="#07101B" stroke="#30E4F3" stroke-width="1.2"/>',
        f'<text x="24" y="32" fill="{CYAN}" font-size="19" font-weight="700" font-family="Segoe UI, sans-serif">SH3DOW // DEVELOPMENT RECORD</text>',
        f'<text x="916" y="32" fill="{DIM}" font-size="12" text-anchor="end" font-family="Segoe UI, sans-serif">TRACKING SINCE {start_year}</text>',
        '<path d="M24 45 H916" stroke="#234458" stroke-width="1"/>',
    ]
    for i, (label, value, color) in enumerate(entries):
        x = 28 + i * 230
        if i:
            parts.append(f'<path d="M{x-15} 58 V148" stroke="#234458" stroke-width="1"/>')
        parts.append(f'<text x="{x}" y="78" fill="{DIM}" font-size="11" font-weight="700" font-family="Segoe UI, sans-serif">{xml(label)}</text>')
        parts.append(f'<text x="{x}" y="122" fill="{color}" font-size="37" font-weight="700" font-family="Segoe UI, sans-serif">{xml(value)}</text>')
    parts.extend([
        '<path d="M24 151 H916" stroke="#234458" stroke-width="1"/>',
        f'<text x="24" y="175" fill="{DIM}" font-size="12" font-family="Segoe UI, sans-serif">Development activity, contributions and technologies across my GitHub projects.</text>',
        '</svg>'
    ])
    write_svg("account-sh3dow.svg", "\n".join(parts))

def language_card(filename, title, subtitle, ranks, denominator, mode, scanned):
    rows = ranks[:8]
    width, height = 470, 310
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        '<rect x="0.5" y="0.5" width="469" height="309" rx="12" fill="#07101B" stroke="#234458"/>',
        f'<text x="22" y="32" fill="{CYAN}" font-size="20" font-weight="700" font-family="Segoe UI, sans-serif">{xml(title)}</text>',
        f'<text x="22" y="53" fill="{DIM}" font-size="12" font-family="Segoe UI, sans-serif">{xml(subtitle)}</text>',
    ]
    if not rows:
        parts.append(f'<text x="24" y="110" fill="{DIM}" font-size="16">No language data returned.</text>')
    for index, (lang, n) in enumerate(rows):
        y = 85 + index * 25
        pct = n / denominator * 100 if denominator else 0
        color = PALETTE[index % len(PALETTE)]
        label = f"{n} repos" if mode == "repos" else f"{pct:.1f}%"
        parts.extend([
            f'<rect x="23" y="{y-10}" width="8" height="8" rx="2" fill="{color}"/>',
            f'<text x="39" y="{y}" fill="{WHITE}" font-size="12" font-family="Segoe UI, sans-serif">{xml(lang[:21])}</text>',
            f'<rect x="198" y="{y-10}" width="163" height="9" rx="4" fill="{BAR}"/>',
            f'<rect x="198" y="{y-10}" width="{max(1, round(163 * min(pct,100)/100))}" height="9" rx="4" fill="{color}"/>',
            f'<text x="451" y="{y}" fill="{DIM}" font-size="12" text-anchor="end" font-family="Segoe UI, sans-serif">{xml(label)}</text>',
        ])
    footer = ("One repository can contain several languages" if mode == "repos" else
              "Distribution based on GitHub language analysis")
    parts.extend([
        '<path d="M22 282 H448" stroke="#234458"/>',
        f'<text x="22" y="299" fill="{DIM}" font-size="11" font-family="Segoe UI, sans-serif">{xml(footer)}</text>',
        '</svg>'
    ])
    write_svg(filename, "\n".join(parts))

def main():
    repositories = collect_repositories()
    if not repositories:
        raise RuntimeError("No repositories are accessible with the configured token.")
    counts = collections.Counter()
    byte_totals = collections.Counter()
    scanned = 0
    for repo in repositories:
        owner = urllib.parse.quote(repo["owner"]["login"], safe="")
        name = urllib.parse.quote(repo["name"], safe="")
        try:
            languages = gh_request(f"/repos/{owner}/{name}/languages")
        except RuntimeError:
            raise RuntimeError("Could not scan all accessible repositories. Refusing partial metrics.") from None
        scanned += 1
        for language, size in languages.items():
            if size > 0:
                counts[language] += 1
                byte_totals[language] += size
    since_year, recognized_total, yearly = collect_contributions()
    account_card(repositories, since_year, recognized_total, yearly, len(counts))
    language_card(
        "languages-sh3dow.svg",
        "LANGUAGES // REPO COVERAGE",
        "In how many repositories each language appears",
        counts.most_common(),
        len(repositories),
        "repos", scanned,
    )
    language_card(
        "languages-bytes-sh3dow.svg",
        "LANGUAGES // CODE VOLUME",
        "Distribution by GitHub-detected source bytes",
        byte_totals.most_common(),
        sum(byte_totals.values()),
        "bytes", scanned,
    )
    print(f"Updated GitHub profile charts from {scanned} accessible repositories and {recognized_total} contributions since {since_year}.")

if __name__ == "__main__":
    main()
