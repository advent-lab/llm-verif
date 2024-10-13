import requests
import os
import sys

'''
Clone repositories off Github
that is written in the HDL of
Verilog or SystemVerilog
'''

def fetch_repositories(target_dir):
    headers = {
        "Authorization": "Bearer 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",
        'Accept': 'application/json',
    }
    base_url = 'https://api.github.com/search/repositories'
    params = {
        'q': 'verilog',
        'per_page': 100
    }
    
    url = base_url
    while url:
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        if response.status_code == 200:
            for repo in data['items']:
                download_repository(repo, target_dir)
            
            # Check the Link header for pagination
            link_header = response.headers.get('Link', '')
            next_url = None
            if 'rel="next"' in link_header:
                # Extract the URL for the next page, remove any surrounding angle brackets
                links = [link.split(';')[0].strip() for link in link_header.split(',') if 'rel="next"' in link]
                if links:
                    next_url = links[0].strip('<>')  # Ensure the URL is cleaned
                    url = next_url
                else:
                    url = None
            else:
                url = None
        else:
            print(f"Failed to fetch repositories. Status code: {response.status_code}")
            break

def download_repository(repo, target_dir):
    os.makedirs(target_dir, exist_ok=True)

    repo_name = repo['full_name']
    clone_url = repo['clone_url']
    repo_dir = os.path.join(target_dir, repo_name.replace('/', '_'))

    if os.path.exists(repo_dir):
        print(f"Skipping {repo_name}, already exists")
    else:
        os.system(f'git clone {clone_url} {repo_dir}')
        print(f"Cloned {repo_name}")

if __name__ == "__main__":
    if len(sys.argv) == 2:
        print("Finding repositories")
        fetch_repositories(sys.argv[1])
    else:
        print(f"Usage: {sys.argv[0]} <path>")
        print(f"Expected: 1 argument, got {len(sys.argv)-1}")
        sys.exit(1)
