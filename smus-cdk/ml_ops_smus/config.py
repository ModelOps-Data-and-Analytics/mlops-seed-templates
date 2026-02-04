from dataclasses import dataclass
from typing import List, Optional

@dataclass
class GitConfig:
    public_smus_aiops_org: str
    public_smus_aiops_org_repo: str
    public_smus_aiops_org_repo_folder: str
    public_repo_branch: str
    oidc_role_github_workflow: str
    private_github_organization: str
    private_deploy_repo_default_branch: str  
    github_token_secret_name: str  
    
    def __init__(
        self,
        public_smus_aiops_org: str,
        public_smus_aiops_org_repo: str,
        public_smus_aiops_org_repo_folder: str,
        public_repo_branch: str,
        oidc_role_github_workflow: str,
        private_github_organization: str,
        private_deploy_repo_default_branch: str,
        github_token_secret_name: str,
        ):
        self.public_smus_aiops_org = public_smus_aiops_org
        self.public_smus_aiops_org_repo = public_smus_aiops_org_repo
        self.public_smus_aiops_org_repo_folder = public_smus_aiops_org_repo_folder
        self.public_repo_branch = public_repo_branch
        self.oidc_role_github_workflow = oidc_role_github_workflow
        self.private_github_organization = private_github_organization
        self.private_deploy_repo_default_branch = private_deploy_repo_default_branch
        self.github_token_secret_name = github_token_secret_name
        

# Single configuration instance
config = GitConfig(
    public_smus_aiops_org="ModelOps-Data-and-Analytics",
    public_smus_aiops_org_repo="mlops-seed-templates",
    public_smus_aiops_org_repo_folder="aiops-seed-code",
    public_repo_branch="main",
    oidc_role_github_workflow="aiops-smus-github-action",
    private_github_organization ="ModelOps-Data-and-Analytics", # IMPORTANT: This should match the GitHub organization configured in your AWS CodeStar Connections and we will be creating our build and deploy repo under this git organization.
    private_deploy_repo_default_branch="main",
    github_token_secret_name="ml-ops-smus-github-token-v2",
)
