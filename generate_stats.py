#!/usr/bin/env python3
"""
GitHub Profile Stats Generator for Sora4431
Generates 4 pairs of SVG cards (dark + light) for the GitHub profile README.

Output files:
  output/assets/svg/overview-dark.svg   / overview-light.svg   (495x195)
  output/assets/svg/charts-dark.svg     / charts-light.svg     (495x195)
  output/assets/svg/activity-dark.svg   / activity-light.svg   (495x195)
  output/assets/svg/monthly-dark.svg    / monthly-light.svg    (1000x200)
"""

import os
import math
import json
import time
import datetime
import requests
from collections import defaultdict

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GITHUB_USER = "Sora4431"
GITHUB_API = "https://api.github.com/graphql"
TOKEN      = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
USE_VIEWER = bool(os.environ.get("STATS_TOKEN"))

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "assets", "svg")

# ---------------------------------------------------------------------------
# Themes
# ---------------------------------------------------------------------------
DARK = {
    "bg":          "transparent",
    "card_bg":     "#161b22",
    "text":        "#e6edf3",
    "muted":       "#8b949e",
    "border":      "#30363d",
    "commits":     "#58a6ff",
    "prs":         "#3fb950",
    "reviews":     "#a371f7",
    "issues":      "#f78166",
    "stars":       "#e3b341",
    "repos":       "#79c0ff",
    "accent":      "#58a6ff",
    "area_fill":   "#58a6ff33",
    "grid":        "#21262d",
    "axis":        "#484f58",
}
LIGHT = {
    "bg":          "transparent",
    "card_bg":     "#f6f8fa",
    "text":        "#24292f",
    "muted":       "#656d76",
    "border":      "#d0d7de",
    "commits":     "#0969da",
    "prs":         "#1a7f37",
    "reviews":     "#8250df",
    "issues":      "#d1242f",
    "stars":       "#9a6700",
    "repos":       "#0550ae",
    "accent":      "#0969da",
    "area_fill":   "#0969da22",
    "grid":        "#eaeef2",
    "axis":        "#8c959f",
}

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_num(n):
    """Format large numbers: 1234 -> '1.2k', 1000000 -> '1M'."""
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def gql_request(query, variables=None):
    """Execute a GitHub GraphQL request."""
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    for attempt in range(4):
        try:
            r = requests.post(GITHUB_API, headers=headers, json=payload, timeout=30)
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
                print(f"GraphQL errors: {data['errors']}")
            return data.get("data", {})
        except Exception as e:
            print(f"Request failed (attempt {attempt + 1}): {e}")
            time.sleep(2 ** attempt)
    return {}


def date_str(dt):
    return dt.strftime("%Y-%m-%dT00:00:00Z")


# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

def build_contrib_query(use_viewer):
    """Build the contributionsCollection fragment query."""
    actor = "viewer" if use_viewer else f'user(login: "{GITHUB_USER}")'
    return f"""
    query($from: DateTime!, $to: DateTime!) {{
      {actor} {{
        contributionsCollection(from: $from, to: $to) {{
          totalCommitContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalIssueContributions
          restrictedContributionsCount
          contributionCalendar {{
            weeks {{
              contributionDays {{
                date
                contributionCount
              }}
            }}
          }}
          commitContributionsByRepository(maxRepositories: 100) {{
            repository {{
              isFork
              languages(first: 10, orderBy: {{field: SIZE, direction: DESC}}) {{
                edges {{
                  size
                  node {{
                    name
                    color
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """


def build_repo_query(use_viewer, after_cursor=None):
    """Build paginated repos query for star/repo count."""
    actor = "viewer" if use_viewer else f'user(login: "{GITHUB_USER}")'
    after = f', after: "{after_cursor}"' if after_cursor else ""
    return f"""
    {{
      {actor} {{
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false{after}) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{
            stargazerCount
            createdAt
          }}
        }}
        createdAt
      }}
    }}
    """


def build_account_query(use_viewer):
    actor = "viewer" if use_viewer else f'user(login: "{GITHUB_USER}")'
    return f"""
    {{
      {actor} {{
        createdAt
      }}
    }}
    """


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_all_contributions():
    """Fetch all-time contributions by chunking into 365-day windows."""
    use_viewer = USE_VIEWER

    # Get account creation date
    data = gql_request(build_account_query(use_viewer))
    actor_key = "viewer" if use_viewer else "user"
    created_str = data.get(actor_key, {}).get("createdAt", "2020-01-01T00:00:00Z")
    created = datetime.datetime.strptime(created_str[:10], "%Y-%m-%d")
    now = datetime.datetime.utcnow()

    totals = {
        "commits": 0,
        "prs": 0,
        "reviews": 0,
        "issues": 0,
    }
    # monthly contributions: key = "YYYY-MM", value = int
    monthly = defaultdict(int)
    # language bytes: key = lang_name, value = {"bytes": int, "color": str}
    lang_bytes = defaultdict(lambda: {"bytes": 0, "color": "#888888"})

    query = build_contrib_query(use_viewer)

    # Chunk from created to now in 365-day windows
    chunk_start = created
    chunk_days = 365

    while chunk_start < now:
        chunk_end = min(chunk_start + datetime.timedelta(days=chunk_days - 1), now)
        variables = {
            "from": date_str(chunk_start),
            "to": date_str(chunk_end),
        }
        print(f"  Fetching contributions {chunk_start.date()} -> {chunk_end.date()} ...")
        data = gql_request(query, variables)
        coll = (data.get("viewer") or data.get("user") or {}).get("contributionsCollection", {})

        totals["commits"]  += coll.get("totalCommitContributions", 0)
        totals["prs"]      += coll.get("totalPullRequestContributions", 0)
        totals["reviews"]  += coll.get("totalPullRequestReviewContributions", 0)
        totals["issues"]   += coll.get("totalIssueContributions", 0)

        # Collect daily contributions -> aggregate to monthly
        for week in coll.get("contributionCalendar", {}).get("weeks", []):
            for day in week.get("contributionDays", []):
                d = day.get("date", "")[:7]  # "YYYY-MM"
                monthly[d] += day.get("contributionCount", 0)

        # Collect language bytes (skip forks)
        for contrib in coll.get("commitContributionsByRepository", []):
            repo = contrib.get("repository", {})
            if repo.get("isFork"):
                continue
            for edge in repo.get("languages", {}).get("edges", []):
                lang = edge.get("node", {})
                name = lang.get("name", "Other")
                color = lang.get("color") or "#888888"
                size = edge.get("size", 0)
                lang_bytes[name]["bytes"] += size
                lang_bytes[name]["color"] = color

        chunk_start = chunk_end + datetime.timedelta(days=1)
        time.sleep(0.2)  # be gentle with the API

    return totals, monthly, lang_bytes


def fetch_repo_stats():
    """Fetch total repo count and total stars earned."""
    use_viewer = USE_VIEWER
    actor_key = "viewer" if use_viewer else "user"
    repo_count = 0
    star_count = 0
    cursor = None

    while True:
        data = gql_request(build_repo_query(use_viewer, cursor))
        repos_data = (data.get(actor_key) or {}).get("repositories", {})
        nodes = repos_data.get("nodes", [])
        repo_count += len(nodes)
        for node in nodes:
            star_count += node.get("stargazerCount", 0)
        page_info = repos_data.get("pageInfo", {})
        if page_info.get("hasNextPage"):
            cursor = page_info.get("endCursor")
        else:
            break
        time.sleep(0.2)

    return repo_count, star_count


# ---------------------------------------------------------------------------
# SVG building utilities
# ---------------------------------------------------------------------------

def svg_open(width, height, theme):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f'<rect width="{width}" height="{height}" rx="6" fill="{theme["card_bg"]}" '
        f'stroke="{theme["border"]}" stroke-width="1"/>\n'
    )


def svg_close():
    return "</svg>\n"


def svg_text(x, y, text, size=12, weight="normal", fill="#e6edf3",
             anchor="start", family=None, opacity=1.0):
    fam = family or FONT
    op = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{op}>'
        f'{text}</text>\n'
    )


def svg_rect(x, y, w, h, fill, rx=3, stroke=None, sw=1, opacity=1.0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{s}{op}/>\n'


def svg_circle(cx, cy, r, fill):
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>\n'


def svg_line(x1, y1, x2, y2, stroke, sw=1, opacity=1.0):
    op = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"{op}/>\n'


def svg_polygon(points, fill, stroke=None, sw=1, opacity=1.0):
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return f'<polygon points="{pts}" fill="{fill}"{s}{op}/>\n'


def svg_path(d, fill="none", stroke=None, sw=1, opacity=1.0):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity != 1.0 else ""
    return f'<path d="{d}" fill="{fill}"{s}{op}/>\n'


# ---------------------------------------------------------------------------
# Card: Overview Stats  (495 x 195)
# ---------------------------------------------------------------------------

def make_overview_svg(theme, totals, repo_count, star_count):
    W, H = 495, 195
    svg = svg_open(W, H, theme)

    # Title
    svg += svg_text(20, 35, "GitHub Stats", size=15, weight="600", fill=theme["text"])

    stats = [
        ("Commits",       fmt_num(totals["commits"]),  theme["commits"]),
        ("Pull Requests",  fmt_num(totals["prs"]),     theme["prs"]),
        ("PR Reviews",    fmt_num(totals["reviews"]),  theme["reviews"]),
        ("Issues",        fmt_num(totals["issues"]),   theme["issues"]),
        ("Stars Earned",  fmt_num(star_count),         theme["stars"]),
        ("Repositories",  fmt_num(repo_count),         theme["repos"]),
    ]

    cols = 3
    rows = 2
    pad_x = 16
    pad_y = 52
    cell_w = (W - pad_x * 2) / cols
    cell_h = (H - pad_y - 12) / rows

    for idx, (label, value, color) in enumerate(stats):
        col = idx % cols
        row = idx // cols
        bx = pad_x + col * cell_w
        by = pad_y + row * cell_h

        # Cell background box
        svg += svg_rect(bx + 2, by + 2, cell_w - 4, cell_h - 4,
                        fill=theme["card_bg"], rx=4,
                        stroke=theme["border"], sw=1)

        # Big colored number
        cx = bx + cell_w / 2
        svg += svg_text(cx, by + cell_h * 0.48, value,
                        size=22, weight="700", fill=color, anchor="middle")
        # Label underneath
        svg += svg_text(cx, by + cell_h * 0.75, label,
                        size=10, weight="400", fill=theme["muted"], anchor="middle")

    svg += svg_close()
    return svg


# ---------------------------------------------------------------------------
# Card: Language Bar + Legend  (495 x 195)
# ---------------------------------------------------------------------------

def make_charts_svg(theme, lang_bytes, top_n=7):
    W, H = 495, 195
    svg = svg_open(W, H, theme)

    # Title
    svg += svg_text(20, 35, "Top Languages", size=15, weight="600", fill=theme["text"])

    # Sort languages by bytes, take top_n
    sorted_langs = sorted(lang_bytes.items(), key=lambda kv: kv[1]["bytes"], reverse=True)[:top_n]
    total_bytes = sum(v["bytes"] for _, v in sorted_langs) or 1

    # Stacked bar
    bar_x = 20
    bar_y = 50
    bar_w = W - 40
    bar_h = 10
    bar_rx = 5

    # Clip path for rounded bar
    svg += f'<defs><clipPath id="bar-clip"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="{bar_rx}"/></clipPath></defs>\n'
    svg += f'<g clip-path="url(#bar-clip)">\n'

    cursor_x = bar_x
    for name, info in sorted_langs:
        pct = info["bytes"] / total_bytes
        seg_w = bar_w * pct
        svg += svg_rect(cursor_x, bar_y, seg_w, bar_h, fill=info["color"], rx=0)
        cursor_x += seg_w
    svg += "</g>\n"

    # Legend (2 columns)
    legend_top = bar_y + bar_h + 14
    dot_r = 5
    cols = 2
    col_w = (W - 40) / cols
    items_per_col = math.ceil(len(sorted_langs) / cols)

    for i, (name, info) in enumerate(sorted_langs):
        col = i // items_per_col
        row = i % items_per_col
        lx = 20 + col * col_w
        ly = legend_top + row * 22

        pct_str = f"{info['bytes'] / total_bytes * 100:.1f}%"

        svg += svg_circle(lx + dot_r, ly + 1, dot_r, info["color"])
        svg += svg_text(lx + dot_r * 2 + 6, ly + 5, name,
                        size=11, fill=theme["text"])
        svg += svg_text(lx + col_w - 4, ly + 5, pct_str,
                        size=11, fill=theme["muted"], anchor="end")

    svg += svg_close()
    return svg


# ---------------------------------------------------------------------------
# Card: Activity Radar Chart  (495 x 195)
# ---------------------------------------------------------------------------

def pentagon_point(cx, cy, radius, axis_index, n_axes=5):
    """Return (x, y) for a pentagon vertex. Axes start from top (-pi/2)."""
    angle = -math.pi / 2 + (2 * math.pi / n_axes) * axis_index
    return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))


def make_activity_svg(theme, totals, repo_count):
    W, H = 495, 195
    svg = svg_open(W, H, theme)

    svg += svg_text(20, 35, "Activity Radar", size=15, weight="600", fill=theme["text"])

    # Axes: Commits, PRs, Reviews, Issues, Repos Contributed
    axes = [
        ("Commits",    totals["commits"],  10000),
        ("PRs",        totals["prs"],      200),
        ("Reviews",    totals["reviews"],  200),
        ("Issues",     totals["issues"],   100),
        ("Repos",      repo_count,         50),
    ]

    n = len(axes)
    cx = 150.0
    cy = 108.0
    max_r = 72.0

    # Draw grid rings at 25%, 50%, 75%, 100%
    for frac in (0.25, 0.50, 0.75, 1.0):
        ring_pts = [pentagon_point(cx, cy, max_r * frac, i, n) for i in range(n)]
        svg += svg_polygon(ring_pts, fill="none",
                           stroke=theme["axis"], sw=0.8, opacity=0.5)

    # Draw axes spokes
    for i in range(n):
        ox, oy = pentagon_point(cx, cy, max_r, i, n)
        svg += svg_line(cx, cy, ox, oy, stroke=theme["axis"], sw=0.8, opacity=0.5)

    # Compute normalized values
    norm = []
    raw_vals = []
    for label, value, benchmark in axes:
        v = min(value / benchmark, 1.0) if benchmark else 0
        norm.append(v)
        raw_vals.append(value)

    # Data polygon
    data_pts = [pentagon_point(cx, cy, max_r * v, i, n) for i, v in enumerate(norm)]
    svg += svg_polygon(data_pts, fill=theme["area_fill"],
                       stroke=theme["accent"], sw=2.0)

    # Dots at vertices
    for x, y in data_pts:
        svg += svg_circle(x, y, 3.5, theme["accent"])

    # Axis labels (pushed slightly outside max ring)
    label_offsets = [
        (0, -10),     # top: Commits
        (10, 4),      # upper-right: PRs
        (6, 14),      # lower-right: Reviews
        (-6, 14),     # lower-left: Issues
        (-10, 4),     # upper-left: Repos
    ]
    for i, (label, value, _) in enumerate(axes):
        lx, ly = pentagon_point(cx, cy, max_r + 16, i, n)
        lx += label_offsets[i][0]
        ly += label_offsets[i][1]
        anchor = "middle"
        if i in (1, 2):
            anchor = "start"
        elif i in (3, 4):
            anchor = "end"
        svg += svg_text(lx, ly, label, size=9, fill=theme["muted"], anchor=anchor)
        svg += svg_text(lx, ly + 11, fmt_num(value), size=9, weight="600",
                        fill=theme["accent"], anchor=anchor)

    # Right side: stat breakdown panel
    panel_x = 285
    panel_y = 50
    row_h = 24

    stat_rows = [
        ("Commits",  fmt_num(totals["commits"]),  theme["commits"]),
        ("PRs",      fmt_num(totals["prs"]),      theme["prs"]),
        ("Reviews",  fmt_num(totals["reviews"]),  theme["reviews"]),
        ("Issues",   fmt_num(totals["issues"]),   theme["issues"]),
        ("Repos",    fmt_num(repo_count),         theme["repos"]),
    ]
    for i, (lbl, val, color) in enumerate(stat_rows):
        ry = panel_y + i * row_h
        svg += svg_rect(panel_x, ry, 190, row_h - 2, fill=theme["grid"], rx=3)
        svg += svg_text(panel_x + 10, ry + 14, lbl,
                        size=10, fill=theme["muted"])
        svg += svg_text(panel_x + 190 - 10, ry + 14, val,
                        size=11, weight="700", fill=color, anchor="end")

    svg += svg_close()
    return svg


# ---------------------------------------------------------------------------
# Card: Monthly Contributions Line Chart  (1000 x 200)
# ---------------------------------------------------------------------------

def make_monthly_svg(theme, monthly):
    W, H = 1000, 200
    svg = svg_open(W, H, theme)

    svg += svg_text(24, 34, "Monthly Contributions", size=15, weight="600", fill=theme["text"])

    # Build last 18 months list
    now = datetime.datetime.utcnow()
    months = []
    for i in range(17, -1, -1):
        m = now - datetime.timedelta(days=i * 30)
        key = m.strftime("%Y-%m")
        label = m.strftime("%b")
        months.append((key, label))

    values = [monthly.get(k, 0) for k, _ in months]
    max_val = max(values) if values else 1
    if max_val == 0:
        max_val = 1

    # Chart area
    chart_l = 48
    chart_r = W - 24
    chart_t = 48
    chart_b = H - 36
    chart_w = chart_r - chart_l
    chart_h = chart_b - chart_t
    n_pts = len(months)

    def pt_x(i):
        return chart_l + i * chart_w / (n_pts - 1) if n_pts > 1 else chart_l

    def pt_y(v):
        return chart_b - (v / max_val) * chart_h

    # Horizontal grid lines
    for frac in (0.25, 0.5, 0.75, 1.0):
        gy = chart_b - frac * chart_h
        gv = int(frac * max_val)
        svg += svg_line(chart_l, gy, chart_r, gy,
                        stroke=theme["axis"], sw=0.6, opacity=0.4)
        svg += svg_text(chart_l - 4, gy + 4, fmt_num(gv),
                        size=8, fill=theme["muted"], anchor="end")

    # Area fill path (closed polygon back to baseline)
    coords = [(pt_x(i), pt_y(v)) for i, v in enumerate(values)]
    area_pts = [f"{chart_l},{chart_b}"]
    for x, y in coords:
        area_pts.append(f"{x:.2f},{y:.2f}")
    area_pts.append(f"{chart_r},{chart_b}")
    svg += f'<polygon points="{" ".join(area_pts)}" fill="{theme["area_fill"]}"/>\n'

    # Smooth line using cubic bezier
    d_parts = [f"M {coords[0][0]:.2f},{coords[0][1]:.2f}"]
    for i in range(1, len(coords)):
        x0, y0 = coords[i - 1]
        x1, y1 = coords[i]
        cp_x = (x0 + x1) / 2
        d_parts.append(f"C {cp_x:.2f},{y0:.2f} {cp_x:.2f},{y1:.2f} {x1:.2f},{y1:.2f}")
    svg += svg_path(" ".join(d_parts), fill="none",
                    stroke=theme["accent"], sw=2.0)

    # Dots at each point
    for i, (x, y) in enumerate(coords):
        svg += svg_circle(x, y, 3, theme["accent"])

    # Month labels
    for i, (key, label) in enumerate(months):
        lx = pt_x(i)
        svg += svg_text(lx, chart_b + 14, label,
                        size=9, fill=theme["muted"], anchor="middle")

    # Baseline
    svg += svg_line(chart_l, chart_b, chart_r, chart_b,
                    stroke=theme["axis"], sw=0.8, opacity=0.6)

    svg += svg_close()
    return svg


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=== Fetching GitHub stats for", GITHUB_USER, "===")

    print("\n[1/2] Fetching contributions...")
    totals, monthly, lang_bytes = fetch_all_contributions()

    print("\n[2/2] Fetching repo/star counts...")
    repo_count, star_count = fetch_repo_stats()

    print(f"\nTotals: commits={totals['commits']}, prs={totals['prs']}, "
          f"reviews={totals['reviews']}, issues={totals['issues']}")
    print(f"Repos: {repo_count}, Stars: {star_count}")
    print(f"Unique months: {len(monthly)}, Languages: {len(lang_bytes)}")

    print("\n=== Generating SVGs ===")

    files = {
        "overview-dark.svg":  make_overview_svg(DARK, totals, repo_count, star_count),
        "overview-light.svg": make_overview_svg(LIGHT, totals, repo_count, star_count),
        "charts-dark.svg":    make_charts_svg(DARK, lang_bytes),
        "charts-light.svg":   make_charts_svg(LIGHT, lang_bytes),
        "activity-dark.svg":  make_activity_svg(DARK, totals, repo_count),
        "activity-light.svg": make_activity_svg(LIGHT, totals, repo_count),
        "monthly-dark.svg":   make_monthly_svg(DARK, monthly),
        "monthly-light.svg":  make_monthly_svg(LIGHT, monthly),
    }

    for name, content in files.items():
        path = os.path.join(OUTPUT_DIR, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  Wrote {path}")

    print("\nDone. All SVGs written to:", OUTPUT_DIR)
    print("\nAdd to your README.md:")
    print("""
<picture>
  <source media="(prefers-color-scheme: dark)"  srcset="output/assets/svg/overview-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="output/assets/svg/overview-light.svg">
  <img src="output/assets/svg/overview-light.svg" alt="GitHub Stats">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)"  srcset="output/assets/svg/charts-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="output/assets/svg/charts-light.svg">
  <img src="output/assets/svg/charts-light.svg" alt="Top Languages">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)"  srcset="output/assets/svg/activity-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="output/assets/svg/activity-light.svg">
  <img src="output/assets/svg/activity-light.svg" alt="Activity Radar">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)"  srcset="output/assets/svg/monthly-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="output/assets/svg/monthly-light.svg">
  <img src="output/assets/svg/monthly-light.svg" alt="Monthly Contributions">
</picture>
""")


if __name__ == "__main__":
    main()
