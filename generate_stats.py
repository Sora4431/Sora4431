import os
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime

GH_TOKEN = os.environ.get('GH_TOKEN', '')
USERNAME = 'Sora4431'

REST_HEADERS = {
    'Authorization': f'Bearer {GH_TOKEN}',
    'Accept': 'application/vnd.github.v3+json',
}
GQL_HEADERS = {
    'Authorization': f'Bearer {GH_TOKEN}',
    'Content-Type': 'application/json',
}

# GitHub Linguist official colors
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
    'Vue':        '#41b883',
    'SCSS':       '#c6538c',
}


def fetch_language_stats():
    repos_url = f'https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner'
    repos = requests.get(repos_url, headers=REST_HEADERS).json()
    lang_totals = {}
    for repo in repos:
        if repo.get('fork'):
            continue
        r = requests.get(
            f'https://api.github.com/repos/{USERNAME}/{repo["name"]}/languages',
            headers=REST_HEADERS,
        )
        if r.ok:
            for lang, size in r.json().items():
                lang_totals[lang] = lang_totals.get(lang, 0) + size
    return lang_totals


def fetch_contribution_stats():
    query = """
    {
      user(login: "%s") {
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
        }
        repositories(ownerAffiliations: OWNER, isFork: false) { totalCount }
        followers { totalCount }
      }
    }
    """ % USERNAME
    r = requests.post(
        'https://api.github.com/graphql',
        json={'query': query},
        headers=GQL_HEADERS,
    )
    if r.ok:
        data = r.json()
        return data.get('data', {}).get('user')
    return None


def generate_language_chart(lang_totals, filename='stats_languages.svg'):
    if not lang_totals:
        print('No language data, skipping chart.')
        return

    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)[:7]
    total = sum(v for _, v in sorted_langs)
    names  = [n for n, _ in sorted_langs]
    pcts   = [v / total * 100 for _, v in sorted_langs]
    colors = [LANG_COLORS.get(n, '#8b949e') for n in names]

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


def generate_stats_card(user_data, filename='stats_overview.svg'):
    cc     = user_data.get('contributionsCollection', {})
    commits = cc.get('totalCommitContributions', 0)
    prs     = cc.get('totalPullRequestContributions', 0)
    issues  = cc.get('totalIssueContributions', 0)
    repos   = user_data.get('repositories', {}).get('totalCount', 0)
    year    = datetime.now().year

    fig, ax = plt.subplots(figsize=(5.2, 3.4))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    ax.axis('off')
    ax.set_title(f'GitHub Stats ({year})', fontsize=13, fontweight='bold',
                 color='#24292e', pad=12)

    stats = [
        ('Commits',       commits, '#0366d6'),
        ('Pull Requests', prs,     '#28a745'),
        ('Issues',        issues,  '#e36209'),
        ('Repositories',  repos,   '#6f42c1'),
    ]
    for i, (label, value, color) in enumerate(stats):
        x = (i % 2) * 0.5 + 0.2
        y = 0.68 - (i // 2) * 0.42
        ax.text(x, y,        str(value), transform=ax.transAxes,
                fontsize=24, fontweight='bold', color=color,
                va='center', ha='center')
        ax.text(x, y - 0.18, label,      transform=ax.transAxes,
                fontsize=9.5, color='#586069',
                va='center', ha='center')

    # subtle divider line
    ax.plot([0.05, 0.95], [0.42, 0.42],
             transform=ax.transAxes, color='#e1e4e8', linewidth=0.8)

    plt.tight_layout(pad=1.2)
    plt.savefig(filename, format='svg', bbox_inches='tight', facecolor='white')
    plt.close()
    print(f'Saved {filename}')


def main():
    print('Fetching language stats...')
    lang_totals = fetch_language_stats()
    print(f'Languages found: {list(lang_totals.keys())}')
    generate_language_chart(lang_totals)

    print('Fetching contribution stats...')
    user_data = fetch_contribution_stats()
    if user_data:
        print(f'Contribution data: {user_data.get("contributionsCollection")}')
        generate_stats_card(user_data)
    else:
        print('Could not fetch contribution stats')


if __name__ == '__main__':
    main()
