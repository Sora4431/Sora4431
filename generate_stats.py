import os
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta

GH_TOKEN = os.environ.get('GH_TOKEN', '')
USERNAME = 'Sora4431'

GQL_HEADERS = {
    'Authorization': f'Bearer {GH_TOKEN}',
    'Content-Type': 'application/json',
}

LANG_COLORS = {
    'TypeScript': '#3178c6',
    'Python':     '#3572A5',
    'JavaScript': '#f1e05a',
    'Ruby':       '#701516',
    'CSS':        '#563d7c',
    'HTML':       '#e34c26',
    'Shell':      '#89e051',
    'Go':         '#00ADD8',
    'Rust':       '#dea584',
    'Java':       '#b07219',
    'C':          '#555555',
    'C++':        '#f34b7d',
    'Swift':      '#F05138',
    'Kotlin':     '#A97BFF',
    'Svelte':     '#ff3e00',
    'Vue':        '#41b883',
    'SCSS':       '#c6538c',
    'Dockerfile': '#384d54',
}


def gql(query):
    r = requests.post(
        'https://api.github.com/graphql',
        json={'query': query},
        headers=GQL_HEADERS,
    )
    r.raise_for_status()
    return r.json().get('data', {})


def fetch_all_stats():
    """Fetch contributions for ENTIRE account history (from creation to now).
    GitHub caps contributionsCollection at 1 year per query, so we chunk yearly.
    """
    # Step 1: get account creation date and repo count
    meta = gql('{ user(login: "%s") { createdAt repositories(ownerAffiliations: OWNER, isFork: false) { totalCount } } }' % USERNAME)
    created_at_str = meta['user']['createdAt']          # e.g. "2025-06-13T02:17:00Z"
    repo_count     = meta['user']['repositories']['totalCount']

    from_dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
    to_dt   = datetime.now(timezone.utc)

    total_commits = 0
    total_prs     = 0
    total_issues  = 0
    all_repo_contribs = []

    # Step 2: iterate in ≤365-day chunks
    chunk_start = from_dt
    while chunk_start < to_dt:
        chunk_end = min(chunk_start + timedelta(days=365), to_dt)

        q = """
        {
          user(login: "%s") {
            contributionsCollection(from: "%s", to: "%s") {
              totalCommitContributions
              totalPullRequestContributions
              totalIssueContributions
              commitContributionsByRepository(maxRepositories: 100) {
                repository {
                  isFork
                  languages(first: 8, orderBy: {field: SIZE, direction: DESC}) {
                    edges { size node { name color } }
                  }
                }
              }
            }
          }
        }
        """ % (USERNAME,
               chunk_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
               chunk_end.strftime('%Y-%m-%dT%H:%M:%SZ'))

        cc = gql(q).get('user', {}).get('contributionsCollection', {})
        total_commits += cc.get('totalCommitContributions', 0)
        total_prs     += cc.get('totalPullRequestContributions', 0)
        total_issues  += cc.get('totalIssueContributions', 0)
        all_repo_contribs.extend(cc.get('commitContributionsByRepository', []))

        chunk_start = chunk_end

    print(f'All-time totals — Commits: {total_commits}, PRs: {total_prs}, Issues: {total_issues}')
    return {
        'commits':       total_commits,
        'prs':           total_prs,
        'issues':        total_issues,
        'repos':         repo_count,
        'repo_contribs': all_repo_contribs,
        'since':         from_dt.strftime('%Y-%m-%d'),
    }


def build_language_totals(repo_contribs):
    lang_totals = {}
    for contrib in repo_contribs:
        repo = contrib.get('repository', {})
        if repo.get('isFork'):
            continue
        for edge in repo.get('languages', {}).get('edges', []):
            name  = edge['node']['name']
            color = edge['node'].get('color')
            size  = edge['size']
            if name not in lang_totals:
                lang_totals[name] = {'size': 0, 'color': color}
            lang_totals[name]['size'] += size
    return lang_totals


def generate_language_chart(lang_totals, filename='stats_languages.svg'):
    if not lang_totals:
        print('No language data.')
        return

    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1]['size'], reverse=True)[:7]
    total  = sum(v['size'] for _, v in sorted_langs)
    names  = [n for n, _ in sorted_langs]
    pcts   = [v['size'] / total * 100 for _, v in sorted_langs]
    colors = [LANG_COLORS.get(n, v['color'] or '#8b949e') for n, v in sorted_langs]

    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')

    y_pos = list(range(len(names)))
    ax.barh(y_pos, pcts, color=colors, height=0.55, edgecolor='none')
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=10.5, color='#24292e')
    ax.invert_yaxis()
    ax.set_xlim(0, max(pcts) * 1.3)
    ax.set_title('Top Languages', fontsize=13, fontweight='bold', color='#24292e', pad=10)

    for i, pct in enumerate(pcts):
        ax.text(pct + 0.5, i, f'{pct:.1f}%', va='center', ha='left',
                fontsize=9.5, color='#586069')

    for spine in ['top', 'right', 'bottom']:
        ax.spines[spine].set_visible(False)
    ax.spines['left'].set_color('#e1e4e8')
    ax.tick_params(length=0, colors='#586069')
    ax.xaxis.set_visible(False)

    plt.tight_layout(pad=1.2)
    plt.savefig(filename, format='svg', bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'Saved {filename}')


def generate_stats_card(stats, filename='stats_overview.svg'):
    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    ax.axis('off')
    ax.set_title(f'GitHub Stats (since {stats["since"]})',
                 fontsize=12, fontweight='bold', color='#24292e', pad=12)

    items = [
        ('Commits',       stats['commits'], '#0366d6'),
        ('Pull Requests', stats['prs'],     '#28a745'),
        ('Issues',        stats['issues'],  '#e36209'),
        ('Repositories',  stats['repos'],   '#6f42c1'),
    ]
    for i, (label, value, color) in enumerate(items):
        x = (i % 2) * 0.5 + 0.2
        y = 0.68 - (i // 2) * 0.42
        ax.text(x, y,        str(value), transform=ax.transAxes,
                fontsize=24, fontweight='bold', color=color, va='center', ha='center')
        ax.text(x, y - 0.18, label, transform=ax.transAxes,
                fontsize=9.5, color='#586069', va='center', ha='center')

    ax.plot([0.05, 0.95], [0.42, 0.42], transform=ax.transAxes,
            color='#e1e4e8', linewidth=0.8)

    plt.tight_layout(pad=1.2)
    plt.savefig(filename, format='svg', bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'Saved {filename}')


def main():
    stats = fetch_all_stats()
    lang_totals = build_language_totals(stats['repo_contribs'])
    print(f'Languages: {list(lang_totals.keys())}')
    generate_language_chart(lang_totals)
    generate_stats_card(stats)


if __name__ == '__main__':
    main()
