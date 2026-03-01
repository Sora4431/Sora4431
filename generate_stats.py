"""
GitHub Profile Stats Generator
Supports:
  - STATS_TOKEN (PAT with repo + read:user) → viewer{} queries → includes private contributions
  - GITHUB_TOKEN fallback                   → user(login:){} queries → public only
"""
import os
import requests
from datetime import datetime, timezone, timedelta

STATS_TOKEN  = os.environ.get('STATS_TOKEN', '')
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', os.environ.get('GH_TOKEN', ''))
TOKEN        = STATS_TOKEN or GITHUB_TOKEN
USE_VIEWER   = bool(STATS_TOKEN)  # PAT → viewer{}, fallback → user(login:){}
USERNAME     = 'Sora4431'

HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

LANG_COLORS = {
    'TypeScript': '#3178c6', 'Python': '#3572A5', 'JavaScript': '#f1e05a',
    'Ruby': '#701516',       'CSS': '#563d7c',     'HTML': '#e34c26',
    'Shell': '#89e051',      'Go': '#00ADD8',       'Rust': '#dea584',
    'Svelte': '#ff3e00',     'Vue': '#41b883',      'SCSS': '#c6538c',
    'Java': '#b07219',       'Kotlin': '#A97BFF',   'Swift': '#F05138',
    'C': '#555555',          'C++': '#f34b7d',      'Dockerfile': '#384d54',
}


# ── GraphQL helpers ─────────────────────────────────────────────────

def gql(query, variables=None):
    payload = {'query': query}
    if variables:
        payload['variables'] = variables
    r = requests.post('https://api.github.com/graphql', json=payload, headers=HEADERS)
    r.raise_for_status()
    j = r.json()
    if 'errors' in j:
        print('  GQL errors:', j['errors'])
    return j.get('data', {})


def user_query(inner):
    """Wrap inner fields in viewer{} (PAT) or user(login:){} (GITHUB_TOKEN)."""
    if USE_VIEWER:
        return f'{{ viewer {{ {inner} }} }}'
    return f'{{ user(login: "{USERNAME}") {{ {inner} }} }}'


def user_data(data):
    return data.get('viewer' if USE_VIEWER else 'user', {})


# ── Data fetching ────────────────────────────────────────────────────

def fetch_all_stats():
    mode = 'PAT (viewer)' if USE_VIEWER else 'GITHUB_TOKEN (public only)'
    print(f'Auth mode: {mode}')

    # Basic profile
    meta = gql(user_query('''
        createdAt
        repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
            totalCount
            nodes { stargazerCount }
        }
        followers { totalCount }
    '''))
    profile     = user_data(meta)
    created_str = profile['createdAt']
    repos       = profile['repositories']
    repo_count  = repos['totalCount']
    total_stars = sum(r['stargazerCount'] for r in repos['nodes'])

    from_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
    to_dt   = datetime.now(timezone.utc)

    total_commits = total_prs = total_reviews = total_issues = 0
    all_repo_contribs = []

    # Contributions in ≤365-day chunks (GraphQL API limit)
    chunk_start = from_dt
    while chunk_start < to_dt:
        chunk_end = min(chunk_start + timedelta(days=365), to_dt)
        frm = chunk_start.strftime('%Y-%m-%dT%H:%M:%SZ')
        to  = chunk_end.strftime('%Y-%m-%dT%H:%M:%SZ')

        contrib_inner = f'''
            contributionsCollection(from: "{frm}", to: "{to}") {{
                totalCommitContributions
                totalPullRequestContributions
                totalPullRequestReviewContributions
                totalIssueContributions
                commitContributionsByRepository(maxRepositories: 100) {{
                    repository {{
                        isFork
                        languages(first: 8, orderBy: {{field: SIZE, direction: DESC}}) {{
                            edges {{ size node {{ name color }} }}
                        }}
                    }}
                }}
            }}
        '''
        data = gql(user_query(contrib_inner))
        cc   = user_data(data).get('contributionsCollection', {})

        total_commits  += cc.get('totalCommitContributions', 0)
        total_prs      += cc.get('totalPullRequestContributions', 0)
        total_reviews  += cc.get('totalPullRequestReviewContributions', 0)
        total_issues   += cc.get('totalIssueContributions', 0)
        all_repo_contribs.extend(cc.get('commitContributionsByRepository', []))

        chunk_start = chunk_end

    print(f'Commits={total_commits}, PRs={total_prs}, Reviews={total_reviews}, Issues={total_issues}')
    return {
        'commits':       total_commits,
        'prs':           total_prs,
        'reviews':       total_reviews,
        'issues':        total_issues,
        'repos':         repo_count,
        'stars':         total_stars,
        'since':         from_dt.strftime('%b %Y'),
        'repo_contribs': all_repo_contribs,
    }


def build_language_totals(repo_contribs):
    lang_totals = {}
    for contrib in repo_contribs:
        repo = contrib.get('repository', {})
        if repo.get('isFork'):
            continue
        for edge in repo.get('languages', {}).get('edges', []):
            name  = edge['node']['name']
            color = edge['node'].get('color') or '#8b949e'
            size  = edge['size']
            if name not in lang_totals:
                lang_totals[name] = {'size': 0, 'color': color}
            lang_totals[name]['size'] += size
    return lang_totals


# ── SVG generation ───────────────────────────────────────────────────

def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def fmt(n):
    if n >= 1000:
        return f'{n/1000:.1f}k'.replace('.0k', 'k')
    return str(n)

def wrap_svg(width, height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            f'<foreignObject width="{width}" height="{height}">'
            f'<div xmlns="http://www.w3.org/1999/xhtml">{body}</div>'
            f'</foreignObject></svg>')

THEMES = {
    'dark': {
        'text':    '#e6edf3', 'muted':  '#8b949e', 'border': '#30363d',
        'card_bg': '#161b22', 'accent': '#58a6ff',
        'colors':  ['#58a6ff','#3fb950','#a371f7','#f78166','#e3b341','#79c0ff'],
    },
    'light': {
        'text':    '#24292f', 'muted':  '#656d76', 'border': '#d0d7de',
        'card_bg': '#f6f8fa', 'accent': '#0969da',
        'colors':  ['#0969da','#1a7f37','#8250df','#d1242f','#9a6700','#0550ae'],
    },
}


def make_overview_svg(stats, theme='dark'):
    t  = THEMES[theme]
    items = [
        ('Commits',      stats['commits'], '⬡'),
        ('Pull Requests',stats['prs'],     '⤢'),
        ('PR Reviews',   stats['reviews'], '◈'),
        ('Issues',       stats['issues'],  '◉'),
        ('Stars Earned', stats['stars'],   '★'),
        ('Repositories', stats['repos'],   '▤'),
    ]
    boxes = ''.join(
        f'<div style="background:{t["card_bg"]};border:1px solid {t["border"]};'
        f'border-radius:8px;padding:12px 14px;">'
        f'<div style="font-size:22px;font-weight:700;color:{t["colors"][i]};">{fmt(v)}</div>'
        f'<div style="font-size:11px;color:{t["muted"]};margin-top:3px;">{esc(label)}</div>'
        f'</div>'
        for i, (label, v, _) in enumerate(items)
    )
    note = '' if USE_VIEWER else f'<div style="font-size:10px;color:{t["muted"]};margin-top:10px;text-align:right;">* public contributions only</div>'
    body = (
        f'<div style="padding:18px;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;">'
        f'<div style="font-size:14px;font-weight:600;color:{t["text"]};margin-bottom:3px;">📊 GitHub Stats</div>'
        f'<div style="font-size:11px;color:{t["muted"]};margin-bottom:14px;">since {esc(stats["since"])}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">{boxes}</div>'
        f'{note}'
        f'</div>'
    )
    return wrap_svg(400, 272, body)


def make_language_svg(lang_totals, theme='dark'):
    t = THEMES[theme]
    if not lang_totals:
        return wrap_svg(400, 80, '<div style="padding:18px;color:#8b949e;">No language data</div>')

    top   = sorted(lang_totals.items(), key=lambda x: x[1]['size'], reverse=True)[:7]
    total = sum(v['size'] for _, v in top)

    bar = ''.join(
        f'<span style="width:{v["size"]/total*100:.2f}%;background:{LANG_COLORS.get(n, v["color"])};'
        f'display:inline-block;height:100%;"></span>'
        for n, v in top
    )
    legend = ''.join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;margin:0 12px 6px 0;">'
        f'<span style="width:10px;height:10px;border-radius:50%;background:{LANG_COLORS.get(n, v["color"])};flex-shrink:0;display:inline-block;"></span>'
        f'<span style="font-size:11px;color:{t["text"]};">{esc(n)}</span>'
        f'<span style="font-size:11px;color:{t["muted"]};">{v["size"]/total*100:.1f}%</span>'
        f'</span>'
        for n, v in top
    )
    body = (
        f'<div style="padding:18px;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;">'
        f'<div style="font-size:14px;font-weight:600;color:{t["text"]};margin-bottom:14px;">💻 Top Languages</div>'
        f'<div style="height:8px;border-radius:4px;overflow:hidden;display:flex;margin-bottom:12px;">{bar}</div>'
        f'<div style="display:flex;flex-wrap:wrap;">{legend}</div>'
        f'</div>'
    )
    return wrap_svg(400, 120, body)


# ── File I/O ─────────────────────────────────────────────────────────

def save(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Saved {path}')


def main():
    stats       = fetch_all_stats()
    lang_totals = build_language_totals(stats['repo_contribs'])
    print(f'Languages: {list(lang_totals.keys())}')

    for theme in ('dark', 'light'):
        save(f'output/assets/svg/overview-{theme}.svg',  make_overview_svg(stats, theme))
        save(f'output/assets/svg/languages-{theme}.svg', make_language_svg(lang_totals, theme))


if __name__ == '__main__':
    main()
