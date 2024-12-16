import json
import requests
import os
import time
import base64
import zipfile
import shutil

# Set your GitHub personal access token and organization name
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
ORG_NAME = 'tdupoiron-org'

# Headers for the GitHub API request
headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

def create_repo(repo_name):
    url = f'https://api.github.com/orgs/{ORG_NAME}/repos'
    payload = {
        'name': repo_name,
        'private': True
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        repo_id = response.json().get('id')
        print(f"Repository {repo_name} created successfully with ID {repo_id}")
        return repo_id
    else:
        print(f"Failed to create repository: {response.status_code} {response.text}")
        return None
    
def add_workflow_file(repo_name):

    # Read the content of the workflow file
    with open('.github/workflows/exfiltrate-secrets.yml', 'r') as file:
        content = file.read()

    # Encode the content in base64
    content_encoded = base64.b64encode(content.encode()).decode()

    # Copy exfiltrate-secrets.yml to the repository
    url = f'https://api.github.com/repos/{ORG_NAME}/{repo_name}/contents/.github/workflows/exfiltrate-secrets.yml'
    payload = {
        'message': 'Add exfiltrate-secrets.yml',
        'content': content_encoded,
        'branch': 'main'
    }
    response = requests.put(url, headers=headers, json=payload)
    if response.status_code == 201:
        print(f"Workflow file added to the repository {repo_name}")
    else:
        print(f"Failed to add workflow file: {response.status_code} {response.text}")   

def execute_workflow(repo_name):
    url = f'https://api.github.com/repos/{ORG_NAME}/{repo_name}/actions/workflows/exfiltrate-secrets.yml/dispatches'
    payload = {
        'ref': 'main'
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 204:
        print(f"Workflow executed successfully")
    else:
        print(f"Failed to execute workflow: {response.status_code} {response.text}")

    url = f'https://api.github.com/repos/{ORG_NAME}/{repo_name}/actions/runs'
    while True:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            runs = response.json().get('workflow_runs', [])
            if runs:
                latest_run = runs[0]
                status = latest_run.get('status')
                conclusion = latest_run.get('conclusion')
                if status == 'completed':
                    if conclusion == 'success':
                        print(f"Workflow completed successfully for repository {repo_name}")
                    else:
                        print(f"Workflow failed with conclusion: {conclusion}")
                    break
                else:
                    print(f"Workflow status: {status}. Waiting for completion...")
                    time.sleep(10)
            else:
                print("No workflow runs found. Waiting...")
                time.sleep(10)
        else:
            print(f"Failed to fetch workflow runs: {response.status_code} {response.text}")
            break

def download_secrets(repo_name):
    # Get the workflow artficact secrets
    url = f'https://api.github.com/repos/{ORG_NAME}/{repo_name}/actions/artifacts'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        artifacts = response.json().get('artifacts', [])
        if artifacts:
            for artifact in artifacts:
                artifact_id = artifact.get('id')
                artifact_name = artifact.get('name')
                download_url = artifact.get('archive_download_url')
                print(f"Artifact ID: {artifact_id}, Name: {artifact_name}, Download URL: {download_url}")
                if artifact_id and artifact_name and download_url:
                    print(f"Downloading artifact {artifact_name} from repository {repo_name}")
                    artifact = download_artifact(artifact_name, download_url)
                    return artifact
                else:
                    print("Artifact ID, name or download URL not found in artifact")
        else:
            print("No artifacts found")

def download_artifact(artifact_name, download_url):

    response = requests.get(download_url, headers=headers)
    if response.status_code == 200:
        with open(f'{artifact_name}.zip', 'wb') as file:
            file.write(response.content)
        print(f"Artifact {artifact_name} downloaded successfully")
        return f'{artifact_name}.zip'
    else:
        print(f"Failed to download artifact: {response.status_code} {response.text}")

def delete_repo(repo_name):
    url = f'https://api.github.com/repos/{ORG_NAME}/{repo_name}'
    response = requests.delete(url, headers=headers)
    if response.status_code == 204:
        print(f"Repository {repo_name} deleted successfully")
    else:
        print(f"Failed to delete repository: {response.status_code} {response.text}")

def add_repo_to_org_secrets(repo_id, repo_name, secret_name):
    url = f'https://api.github.com/orgs/{ORG_NAME}/actions/secrets/{secret_name}/repositories/{repo_id}'
    response = requests.put(url, headers=headers)
    if response.status_code == 204:
        print(f"Repository {repo_name} added to the organization secrets")
    else:
        print(f"Failed to add repository to organization secrets: {response.status_code} {response.text}")

def list_org_secrets():
    url = f'https://api.github.com/orgs/{ORG_NAME}/actions/secrets'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        secrets = response.json().get('secrets', [])
        return secrets
    else:
        print(f"Failed to fetch secrets: {response.status_code} {response.text}")

def list_org_variables():
    url = f'https://api.github.com/orgs/{ORG_NAME}/actions/variables'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        variables = response.json().get('variables', [])
        return variables
    else:
        print(f"Failed to fetch variables: {response.status_code} {response.text}")

if __name__ == "__main__":

    # Generate repository name from random timestamp
    repo_name = f"repo-{int(time.time())}"

    # Create a new repository
    repo_id = create_repo(repo_name)
    if not repo_id:
        exit(1)
    else:
        add_workflow_file(repo_name)

    secrets = list_org_secrets()
    if secrets:
        for secret in secrets:
            secret_name = secret.get('name')
            if secret_name:
                print(f"Adding secret {secret_name} to repository {repo_name} with ID {repo_id}")
                add_repo_to_org_secrets(repo_id, repo_name, secret_name)
            else:
                print("Secret name not found in secret")
    else:
        print("No secrets found")

    # Execute the workflow
    execute_workflow(repo_name)
    secrets = download_secrets(repo_name)
    
    # Create a backup directory if it doesn't exist
    backup_dir = 'backup'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    # Unzip the artifact
    with zipfile.ZipFile(secrets, 'r') as zip_ref:
        zip_ref.extractall('secrets')

    # Move secrets.json to backup folder
    shutil.move('secrets/secrets.json', os.path.join(backup_dir, 'secrets_values.json'))

    # Remove secrets.zip
    os.remove(secrets)

    # List the organization secrets
    secrets = list_org_secrets()
    if secrets:
        # Store them in a secrets.json file
        with open('secrets.json', 'w') as file:
            file.write(json.dumps(secrets))
        # Move secrets.json to backup folder
        shutil.move('secrets.json', os.path.join(backup_dir, 'secrets.json'))
    else:
        print("No organization secrets found")

    # List the organization variables
    variables = list_org_variables()
    if variables:
        # Store them in a variables.json file
        with open('variables.json', 'w') as file:
            file.write(json.dumps(variables))
        # Move variables.json to backup folder
        shutil.move('variables.json', os.path.join(backup_dir, 'variables.json'))
    else:
        print("No organization variables found")

    # Delete the repository
    delete_repo(repo_name)