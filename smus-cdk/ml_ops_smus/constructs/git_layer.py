import os
import subprocess
from constructs import Construct
from aws_cdk import aws_lambda as _lambda

class GitLayerConstruct(Construct):
    def __init__(self, scope: Construct, id: str) -> None:
        super().__init__(scope, id)

        dist_path = self._build_git_layer()
        print(f"Git layer built at: {dist_path}")

        # Create Lambda layer from the extracted directory
        self.layer = _lambda.LayerVersion(
            self, "Layer",
            code=_lambda.Code.from_asset(dist_path),
            description="Minimal Git binary layer",
            layer_version_name="ml-ops-smus-git-layer",
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
        )

    def _build_git_layer(self) -> str:
        project_root = os.getcwd()
        dist_path = os.path.join(project_root, "dist", "layer")
        docker_context = os.path.join(project_root, "layers", "git-layer")

        os.makedirs(dist_path, exist_ok=True)

        try:
            # Use podman instead of docker
            container_cmd = "podman" if subprocess.run(["which", "podman"], capture_output=True).returncode == 0 else "docker"
            
            # Build container image
            subprocess.run(
                [container_cmd, "build", "-t", "git-layer-builder", docker_context],
                check=True
            )

            # Run container to get tar file
            subprocess.run(
                [container_cmd, "run", "--rm", "-v", f"{dist_path}:/output", "git-layer-builder"],
                check=True
            )

            # Extract tar file
            subprocess.run(
                ["tar", "xzf", os.path.join(dist_path, "git.tar.gz"), "-C", dist_path],
                check=True
            )

            # Clean up tar file
            os.unlink(os.path.join(dist_path, "git.tar.gz"))

            return dist_path

        except subprocess.CalledProcessError as e:
            print(f"Error during build: {str(e)}")
            raise
