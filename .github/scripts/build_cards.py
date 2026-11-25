"""Build pastel GitHub stats cards for the profile README.

Runs inside GitHub Actions (see .github/workflows/cards.yml) and writes
SVG files into assets/. Needs GITHUB_TOKEN and USERNAME in the environment.
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from html import escape

USER = os.environ.get("USERNAME", "shahadeissaalharbi")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "assets")

BG = "#fdf2f7"
BORDER = "#f3d6e4"
TITLE = "#8a4fa8"
TEXT = "#4a3550"
MUTED = "#8c7894"
LEVELS = ["#f3eef6", "#f6c9dc", "#e9a3c4", "#c58ad9", "#8a5cb8"]
LANG_COLORS = ["#c58ad9", "#e9a3c4", "#9fd8c4", "#f7c59f", "#a9c7f0", "#f6e3a1"]
FONT = "font-family=\"'Segoe UI', Ubuntu, Helvetica, Arial, sans-serif\""


def gql(query, variables=None):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables or {}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        sys.exit(f"GraphQL error: {body['errors']}")
    return body["data"]


def fetch():
    d = gql(
        """query($u:String!){user(login:$u){
          pullRequests{totalCount}
          repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){totalCount}
          repositories(ownerAffiliations:OWNER,first:100,isFork:false){nodes{
            stargazerCount
            languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}
          contributionsCollection{totalCommitContributions contributionYears
            contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}""",
        {"u": USER},
    )["user"]
    days = {}
    total_all = 0
    for year in d["contributionsCollection"]["contributionYears"]:
        y = gql(
            """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
              contributionsCollection(from:$f,to:$t){contributionCalendar{
                totalContributions weeks{contributionDays{date contributionCount}}}}}}""",
            {"u": USER, "f": f"{year}-01-01T00:00:00Z", "t": f"{year}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]["contributionCalendar"]
        total_all += y["totalContributions"]
        for w in y["weeks"]:
            for day in w["contributionDays"]:
                days[day["date"]] = day["contributionCount"]
    langs = {}
    stars = 0
    for repo in d["repositories"]["nodes"]:
        stars += repo["stargazerCount"]
        for e in repo["languages"]["edges"]:
            langs[e["node"]["name"]] = langs.get(e["node"]["name"], 0) + e["size"]
    return {
        "stars": stars,
        "commits": d["contributionsCollection"]["totalCommitContributions"],
        "prs": d["pullRequests"]["totalCount"],
        "contributed": d["repositoriesContributedTo"]["totalCount"],
        "langs": langs,
        "days": days,
        "total_all": total_all,
        "calendar": d["contributionsCollection"]["contributionCalendar"]["weeks"],
    }


def streaks(days):
    today = date.today()
    ordered = sorted(days)
    longest = run = 0
    for ds in ordered:
        run = run + 1 if days[ds] > 0 else 0
        longest = max(longest, run)
    current = 0
    d = today if days.get(today.isoformat(), 0) > 0 else today - timedelta(days=1)
    while days.get(d.isoformat(), 0) > 0:
        current += 1
        d -= timedelta(days=1)
    return current, longest


def card(width, height, title, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<style>.t{{animation:f .8s ease-out both}}@keyframes f{{from{{opacity:0}}to{{opacity:1}}}}</style>'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f'<text x="24" y="38" {FONT} font-size="18" font-weight="700" fill="{TITLE}">{escape(title)}</text>'
        f"{body}</svg>"
    )


def stats_svg(s):
    rows = [
        ("Total stars", s["stars"]),
        ("Commits (last year)", s["commits"]),
        ("Pull requests", s["prs"]),
        ("Contributed to", s["contributed"]),
    ]
    body = ""
    for i, (label, value) in enumerate(rows):
        y = 74 + i * 30
        body += (
            f'<g class="t" style="animation-delay:{i * 0.15}s">'
            f'<circle cx="30" cy="{y - 5}" r="5" fill="{LEVELS[2 + i % 3]}"/>'
            f'<text x="44" y="{y}" {FONT} font-size="14" fill="{TEXT}">{label}</text>'
            f'<text x="300" y="{y}" {FONT} font-size="14" font-weight="700" fill="{TITLE}" text-anchor="end">{value}</text></g>'
        )
    return card(330, 190, "Shahad's GitHub Stats", body)


def langs_svg(s):
    top = sorted(s["langs"].items(), key=lambda kv: -kv[1])[:6]
    total = sum(v for _, v in top) or 1
    body, x = "", 24
    bar_w = 282
    body += f'<clipPath id="c"><rect x="24" y="58" width="{bar_w}" height="10" rx="5"/></clipPath><g clip-path="url(#c)">'
    for i, (_, v) in enumerate(top):
        w = bar_w * v / total
        body += f'<rect x="{x:.1f}" y="58" width="{w:.1f}" height="10" fill="{LANG_COLORS[i]}"/>'
        x += w
    body += "</g>"
    for i, (name, v) in enumerate(top):
        cx = 24 + (i % 2) * 150
        cy = 98 + (i // 2) * 28
        body += (
            f'<g class="t" style="animation-delay:{i * 0.12}s">'
            f'<circle cx="{cx + 5}" cy="{cy - 5}" r="5" fill="{LANG_COLORS[i]}"/>'
            f'<text x="{cx + 16}" y="{cy}" {FONT} font-size="13" fill="{TEXT}">{escape(name)} '
            f'<tspan fill="{MUTED}">{100 * v / total:.1f}%</tspan></text></g>'
        )
    return card(330, 190, "Most used languages", body)


def streak_svg(s):
    current, longest = streaks(s["days"])
    cols = [("Total contributions", s["total_all"]), ("Current streak", current), ("Longest streak", longest)]
    body = ""
    for i, (label, value) in enumerate(cols):
        cx = 110 + i * 220
        body += (
            f'<g class="t" style="animation-delay:{i * 0.2}s">'
            f'<text x="{cx}" y="44" {FONT} font-size="28" font-weight="700" fill="{TITLE}" text-anchor="middle">{value}</text>'
            f'<text x="{cx}" y="72" {FONT} font-size="13" fill="{TEXT}" text-anchor="middle">{label}</text></g>'
        )
        if i:
            body += f'<line x1="{cx - 110}" y1="22" x2="{cx - 110}" y2="78" stroke="{BORDER}" stroke-width="2"/>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="680" height="100" viewBox="0 0 680 100">'
        f'<style>.t{{animation:f .8s ease-out both}}@keyframes f{{from{{opacity:0}}to{{opacity:1}}}}</style>'
        f'<rect x="0.5" y="0.5" width="679" height="99" rx="12" fill="{BG}" stroke="{BORDER}"/>{body}</svg>'
    )


def activity_svg(s):
    weeks = s["calendar"]
    peak = max([d["contributionCount"] for w in weeks for d in w["contributionDays"]] + [1])
    cell, gap = 11, 3
    width = 24 * 2 + len(weeks) * (cell + gap)
    height = 24 * 2 + 7 * (cell + gap)
    body = ""
    for wi, w in enumerate(weeks):
        for day in w["contributionDays"]:
            dow = (date.fromisoformat(day["date"]).weekday() + 1) % 7
            c = day["contributionCount"]
            lvl = 0 if c == 0 else min(4, 1 + int(3 * c / peak))
            body += (
                f'<rect x="{24 + wi * (cell + gap)}" y="{24 + dow * (cell + gap)}" width="{cell}" height="{cell}" '
                f'rx="2.5" fill="{LEVELS[lvl]}"><title>{day["date"]}: {c}</title></rect>'
            )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>'
        f"{body}</svg>"
    )


def main():
    s = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [("stats", stats_svg), ("langs", langs_svg), ("streak", streak_svg), ("activity", activity_svg)]:
        with open(os.path.join(OUT, f"{name}.svg"), "w") as f:
            f.write(fn(s))
    print("cards written")


if __name__ == "__main__":
    main()
