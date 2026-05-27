import os
import json
import shutil
import zipfile
import logging
import threading
import time
from typing import Optional
import docker
from docker.errors import NotFound, APIError
from app.config import settings

logger = logging.getLogger(__name__)

# Junk directories/files to auto-remove before Docker build
SANITIZE_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git", "__MACOSX", ".pytest_cache"}
SANITIZE_FILES = {"pnpm-lock.yaml", ".DS_Store"}
# Cross-platform lock files that may cause issues
CROSS_PLATFORM_LOCKS = {"pnpm-lock.yaml"}

# Build timeout in seconds (3 minutes)
BUILD_TIMEOUT_SECONDS = 180

# Build log storage for SSE streaming
_build_logs: dict[str, list[str]] = {}
_build_status: dict[str, str] = {}  # "building", "success", "error", "timeout"

DOCKERFILE_TEMPLATES = {
    "nodejs": """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production
COPY . .
EXPOSE {port}
CMD ["npm", "start"]
""",
    "python": """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port}
CMD ["python", "main.py"]
""",
    "python_streamlit": """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port}
CMD ["streamlit", "run", "app.py", "--server.port={port}", "--server.address=0.0.0.0"]
""",
    "python_fastapi": """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE {port}
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "{port}"]
""",
    "fullstack": None,  # Generated dynamically in _generate_fullstack_files()
    "static": """FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
""",
    "static_prebuilt": """FROM nginx:alpine
COPY dist/ /usr/share/nginx/html
EXPOSE 80
""",
    "nodejs_vite": """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE {port}
CMD ["npx", "vite", "preview", "--port", "{port}", "--host"]
""",
}


class DockerService:
    def __init__(self):
        self.client = None
        self._connect()

    def _connect(self):
        """Try to connect to Docker daemon."""
        try:
            self.client = docker.from_env()
            # Test connection by pinging
            self.client.ping()
            self._ensure_network()
            logger.info("Docker connected successfully")
        except Exception as e:
            logger.warning(f"Docker not available: {e}")
            self.client = None

    def _ensure_client(self) -> bool:
        """Ensure Docker client is connected. Try reconnect if needed."""
        if self.client:
            try:
                self.client.ping()
                return True
            except Exception:
                logger.warning("Docker connection lost, attempting reconnect...")
                self.client = None

        self._connect()
        return self.client is not None

    def is_available(self) -> bool:
        """Check if Docker daemon is available."""
        return self._ensure_client()

    def _ensure_network(self):
        if not self.client:
            return
        try:
            self.client.networks.get(settings.DOCKER_NETWORK)
        except NotFound:
            self.client.networks.create(settings.DOCKER_NETWORK, driver="bridge")

    def sanitize_source(self, source_path: str) -> dict:
        """Auto-remove junk directories and files before Docker build.
        Returns a summary of what was removed."""
        removed = {"dirs": [], "files": [], "size_freed_mb": 0}

        for root, dirs, files in os.walk(source_path, topdown=True):
            # Remove junk directories
            for d in list(dirs):
                if d in SANITIZE_DIRS:
                    dir_path = os.path.join(root, d)
                    try:
                        dir_size = sum(
                            os.path.getsize(os.path.join(dp, f))
                            for dp, _, fns in os.walk(dir_path) for f in fns
                        )
                        shutil.rmtree(dir_path)
                        rel_path = os.path.relpath(dir_path, source_path)
                        removed["dirs"].append(rel_path)
                        removed["size_freed_mb"] += dir_size / (1024 * 1024)
                        logger.info(f"Auto-sanitize: removed {rel_path} ({dir_size / 1024 / 1024:.1f} MB)")
                        dirs.remove(d)
                    except Exception as e:
                        logger.warning(f"Failed to remove {d}: {e}")

            # Remove junk files
            for f in files:
                if f in SANITIZE_FILES:
                    file_path = os.path.join(root, f)
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        rel_path = os.path.relpath(file_path, source_path)
                        removed["files"].append(rel_path)
                        removed["size_freed_mb"] += file_size / (1024 * 1024)
                    except Exception as e:
                        logger.warning(f"Failed to remove {f}: {e}")

        # Also remove cross-platform lock files at root level
        for lock_file in CROSS_PLATFORM_LOCKS:
            lock_path = os.path.join(source_path, lock_file)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                    if lock_file not in removed["files"]:
                        removed["files"].append(lock_file)
                        logger.info(f"Auto-sanitize: removed cross-platform lock {lock_file}")
                except Exception as e:
                    logger.warning(f"Failed to remove lock file {lock_file}: {e}")

        removed["size_freed_mb"] = round(removed["size_freed_mb"], 1)
        if removed["dirs"] or removed["files"]:
            logger.info(f"Auto-sanitize complete: freed {removed['size_freed_mb']} MB, "
                        f"removed {len(removed['dirs'])} dirs, {len(removed['files'])} files")
        return removed

    def detect_app_type(self, source_path: str) -> str:
        files = os.listdir(source_path)

        # Fullstack: has both backend/ and frontend/ directories
        has_backend = os.path.isdir(os.path.join(source_path, "backend"))
        has_frontend = os.path.isdir(os.path.join(source_path, "frontend"))
        if has_backend and has_frontend:
            backend_main = os.path.join(source_path, "backend", "main.py")
            frontend_dist = os.path.join(source_path, "frontend", "dist")
            frontend_pkg = os.path.join(source_path, "frontend", "package.json")
            if os.path.exists(backend_main) and (os.path.isdir(frontend_dist) or os.path.exists(frontend_pkg)):
                return "fullstack"

        if "package.json" in files:
            pkg_path = os.path.join(source_path, "package.json")
            try:
                with open(pkg_path, "r") as f:
                    pkg = json.load(f)

                # Check if this is a Vite/static build project
                dev_deps = pkg.get("devDependencies", {})
                deps = pkg.get("dependencies", {})
                scripts = pkg.get("scripts", {})
                start_script = scripts.get("start", "")
                build_script = scripts.get("build", "")

                is_vite = "vite" in dev_deps or "vite" in deps
                has_vite_build = "vite build" in build_script or "vite" in build_script
                has_vite_preview = "vite preview" in start_script

                # If it has a pre-built dist/ with index.html, treat as static
                dist_dir = os.path.join(source_path, "dist")
                if os.path.isdir(dist_dir) and os.path.exists(os.path.join(dist_dir, "index.html")):
                    logger.info("Detected pre-built Vite/static app with dist/ folder")
                    return "static_prebuilt"

                # If it's a Vite project with vite preview as start script
                if is_vite and has_vite_preview:
                    logger.info("Detected Vite app with 'vite preview' start script")
                    return "nodejs"  # Will use npm start which runs vite preview

                # If it's a Vite project without proper start script, suggest build
                if is_vite and has_vite_build and not has_vite_preview:
                    logger.info("Detected Vite project — needs build + serve setup")
                    return "nodejs_vite"

            except Exception:
                pass

            return "nodejs"

        if "requirements.txt" in files or "main.py" in files:
            if "app.py" in files:
                req_path = os.path.join(source_path, "requirements.txt")
                if os.path.exists(req_path):
                    with open(req_path, "r", errors="ignore") as f:
                        content = f.read()
                    if "streamlit" in content:
                        return "python_streamlit"
            if "main.py" in files:
                with open(os.path.join(source_path, "main.py"), "r", errors="ignore") as f:
                    content = f.read()
                if "fastapi" in content.lower() or "FastAPI" in content:
                    return "python_fastapi"
            return "python"
        if "index.html" in files:
            return "static"
        return "static"

    def extract_zip(self, zip_path: str, dest_path: str) -> str:
        os.makedirs(dest_path, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_path)

        entries = os.listdir(dest_path)
        non_hidden = [e for e in entries if not e.startswith(".") and not e.startswith("__")]
        if len(non_hidden) == 1 and os.path.isdir(os.path.join(dest_path, non_hidden[0])):
            inner = os.path.join(dest_path, non_hidden[0])
            for item in os.listdir(inner):
                shutil.move(os.path.join(inner, item), os.path.join(dest_path, item))
            os.rmdir(inner)

        return dest_path

    def generate_dockerfile(self, source_path: str, app_type: str, port: int) -> str:
        # Skip user-provided Dockerfile for auto-detected fullstack apps
        if app_type != "fullstack" and os.path.exists(os.path.join(source_path, "Dockerfile")):
            return os.path.join(source_path, "Dockerfile")

        if app_type == "fullstack":
            return self._generate_fullstack_files(source_path, port)

        template_key = app_type
        if template_key not in DOCKERFILE_TEMPLATES:
            template_key = "static"

        content = DOCKERFILE_TEMPLATES[template_key].format(port=port)

        if app_type == "nodejs":
            pkg_path = os.path.join(source_path, "package.json")
            if os.path.exists(pkg_path):
                with open(pkg_path, "r") as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                if "start" not in scripts:
                    if "dev" in scripts:
                        content = content.replace('CMD ["npm", "start"]', 'CMD ["npm", "run", "dev"]')
                    elif "main" in pkg:
                        main_file = pkg["main"]
                        content = content.replace('CMD ["npm", "start"]', f'CMD ["node", "{main_file}"]')

        dockerfile_path = os.path.join(source_path, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write(content)
        return dockerfile_path

    def _generate_fullstack_files(self, source_path: str, port: int) -> str:
        """Generate Dockerfile + nginx.conf + start.sh for fullstack apps."""

        # Check if frontend has a NON-EMPTY pre-built dist/
        # (an empty dist/ directory triggers the nginx welcome-page bug — IVS-#fullstack-empty-dist)
        frontend_dist = os.path.join(source_path, "frontend", "dist")
        has_dist = os.path.isdir(frontend_dist) and any(os.scandir(frontend_dist))

        # Nginx config — strip /api prefix so /api/foo -> backend /foo
        nginx_conf = f"""server {{
    listen {port};
    root /usr/share/nginx/html;
    index index.html;

    location /api/ {{
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        client_max_body_size 200m;
    }}

    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
"""
        with open(os.path.join(source_path, "nginx-app.conf"), "w") as f:
            f.write(nginx_conf)

        # Start script
        start_sh = """#!/bin/bash
cd /app/backend
uvicorn main:app --host 127.0.0.1 --port 8000 &
echo "Backend started on :8000"
nginx -g 'daemon off;'
"""
        with open(os.path.join(source_path, "start-app.sh"), "w") as f:
            f.write(start_sh)

        # Build Dockerfile — use multi-stage build for fullstack apps.
        # - If pre-built dist/ exists (non-empty): use fast path, copy dist/ directly.
        # - Otherwise: spin up a Node.js builder stage to run `npm run build`.
        # Both paths avoid installing Node in the runtime image (keeps image small).
        if has_dist:
            # Fast path: user already ran `npm run build` locally
            builder_stage = ""
            frontend_copy = "COPY frontend/dist/ /usr/share/nginx/html/"
        else:
            # Auto-build path: multi-stage build runs `npm run build` in node:20-alpine
            builder_stage = """# ===== Stage 1: Build frontend (Vite/React/etc.) =====
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ===== Stage 2: Production runtime =====
"""
            frontend_copy = "COPY --from=frontend-builder /build/dist/ /usr/share/nginx/html/"

        dockerfile = f"""{builder_stage}FROM python:3.12-slim

# Install nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Backend setup
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./

# Frontend setup
{frontend_copy}

# Remove nginx default welcome page (prevents fallback if frontend files miss)
RUN rm -f /usr/share/nginx/html/index.nginx-debian.html

# Nginx config
COPY nginx-app.conf /etc/nginx/sites-available/default

# Startup script
COPY start-app.sh /start-app.sh
RUN chmod +x /start-app.sh

EXPOSE {port}
CMD ["/start-app.sh"]
"""
        dockerfile_path = os.path.join(source_path, "Dockerfile")
        with open(dockerfile_path, "w") as f:
            f.write(dockerfile)

        # Write .dockerignore to skip junk files
        dockerignore = ".git\n__MACOSX\n.DS_Store\n*.pyc\n__pycache__\n.venv\nnode_modules\n.pytest_cache\n"
        with open(os.path.join(source_path, ".dockerignore"), "w") as f:
            f.write(dockerignore)

        logger.info(f"Generated fullstack Dockerfile (multi-stage, dist={'pre-built' if has_dist else 'auto-build'})")
        return dockerfile_path

    def get_build_logs(self, app_slug: str) -> list[str]:
        """Get stored build logs for an app."""
        return _build_logs.get(app_slug, [])

    def get_build_status(self, app_slug: str) -> str:
        """Get build status: building, success, error, timeout."""
        return _build_status.get(app_slug, "unknown")

    def _append_build_log(self, app_slug: str, message: str):
        """Append a log line for SSE streaming."""
        if app_slug not in _build_logs:
            _build_logs[app_slug] = []
        _build_logs[app_slug].append(message)

    def build_and_run(
        self,
        app_slug: str,
        source_path: str,
        app_type: str,
        port: int,
        env_vars: Optional[dict] = None,
    ) -> Optional[str]:
        if not self._ensure_client():
            raise RuntimeError("Docker Desktop is not running. Please start Docker Desktop and try again.")

        image_tag = f"ivs-app-{app_slug}:latest"
        container_name = f"ivs-{app_slug}"

        # Initialize build log
        _build_logs[app_slug] = []
        _build_status[app_slug] = "building"

        self._append_build_log(app_slug, f"[IVS] Preparing deployment for {app_slug}...")
        self.stop_and_remove(container_name)

        # Auto-sanitize: remove junk files
        self._append_build_log(app_slug, "[IVS] Auto-sanitize: scanning for junk files...")
        sanitize_result = self.sanitize_source(source_path)
        if sanitize_result["dirs"] or sanitize_result["files"]:
            for d in sanitize_result["dirs"]:
                self._append_build_log(app_slug, f"[IVS] ✓ Removed directory: {d}")
            for f in sanitize_result["files"]:
                self._append_build_log(app_slug, f"[IVS] ✓ Removed file: {f}")
            self._append_build_log(app_slug, f"[IVS] Auto-sanitize freed {sanitize_result['size_freed_mb']} MB")
        else:
            self._append_build_log(app_slug, "[IVS] ✓ No junk files found — source is clean")

        self._append_build_log(app_slug, f"[IVS] Generating Dockerfile for type: {app_type}")
        self.generate_dockerfile(source_path, app_type, port)

        # Build with timeout
        build_error = None
        build_done = threading.Event()

        def do_build():
            nonlocal build_error
            try:
                self._append_build_log(app_slug, f"[IVS] Building Docker image {image_tag}...")
                image, build_logs = self.client.images.build(
                    path=source_path,
                    tag=image_tag,
                    rm=True,
                    forcerm=True,
                )
                for log in build_logs:
                    if "stream" in log:
                        line = log["stream"].strip()
                        if line:
                            self._append_build_log(app_slug, line)
                            logger.debug(line)
                self._append_build_log(app_slug, "[IVS] ✓ Docker image built successfully")
            except Exception as e:
                build_error = e
                self._append_build_log(app_slug, f"[IVS] ✗ Build error: {str(e)[:200]}")
                logger.error(f"Build failed for {app_slug}: {e}")
            finally:
                build_done.set()

        build_thread = threading.Thread(target=do_build, daemon=True)
        build_thread.start()

        # Wait with timeout
        if not build_done.wait(timeout=BUILD_TIMEOUT_SECONDS):
            _build_status[app_slug] = "timeout"
            self._append_build_log(app_slug, f"[IVS] ✗ Build timeout! Exceeded {BUILD_TIMEOUT_SECONDS}s limit.")
            self._append_build_log(app_slug, "[IVS] The build was cancelled to protect the server.")
            # Try to clean up
            try:
                self.client.api.prune_builds()
            except Exception:
                pass
            raise RuntimeError(
                f"Build timeout: exceeded {BUILD_TIMEOUT_SECONDS // 60} minutes. "
                f"This may be caused by node_modules in the ZIP or a very large project. "
                f"Please remove unnecessary files and try again."
            )

        if build_error:
            _build_status[app_slug] = "error"
            raise build_error

        internal_port = 80 if app_type in ("static", "static_prebuilt") else port
        environment = env_vars or {}
        environment["PORT"] = str(port)

        try:
            self._append_build_log(app_slug, f"[IVS] Starting container {container_name} on port {port}...")
            container = self.client.containers.run(
                image_tag,
                name=container_name,
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                ports={f"{internal_port}/tcp": port},
                environment=environment,
                network=settings.DOCKER_NETWORK,
                labels={
                    "ivs.managed": "true",
                    "ivs.app": app_slug,
                    "ivs.type": app_type,
                },
            )
            self._append_build_log(app_slug, f"[IVS] ✓ Container started: {container.short_id}")
            _build_status[app_slug] = "success"
            logger.info(f"Container {container_name} started: {container.short_id}")
            return container.id
        except Exception as e:
            _build_status[app_slug] = "error"
            self._append_build_log(app_slug, f"[IVS] ✗ Container start failed: {str(e)[:200]}")
            logger.error(f"Run failed for {app_slug}: {e}")
            raise

    def stop_and_remove(self, container_name: str):
        if not self.client:
            return
        try:
            container = self.client.containers.get(container_name)
            container.stop(timeout=10)
            container.remove()
        except NotFound:
            pass
        except Exception as e:
            logger.warning(f"Error stopping {container_name}: {e}")

    def stop_container(self, container_id: str):
        if not self.client:
            return
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=10)
        except Exception as e:
            logger.warning(f"Error stopping container {container_id}: {e}")

    def start_container(self, container_id: str):
        if not self.client:
            return
        try:
            container = self.client.containers.get(container_id)
            container.start()
        except Exception as e:
            logger.warning(f"Error starting container {container_id}: {e}")

    def restart_container(self, container_id: str):
        if not self.client:
            return
        try:
            container = self.client.containers.get(container_id)
            container.restart(timeout=10)
        except Exception as e:
            logger.warning(f"Error restarting container {container_id}: {e}")

    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        if not self.client:
            return "Docker not available"
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")
        except Exception as e:
            return f"Error getting logs: {e}"

    def get_container_stats(self, container_id: str) -> dict:
        if not self.client:
            return {}
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100.0 if system_delta > 0 else 0.0
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 1)
            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage": mem_usage,
                "memory_limit": mem_limit,
                "memory_percent": round((mem_usage / mem_limit) * 100, 2) if mem_limit > 0 else 0,
            }
        except Exception:
            return {}

    def get_running_app_count(self) -> tuple[int, int]:
        if not self.client:
            return 0, 0
        try:
            containers = self.client.containers.list(all=True, filters={"label": "ivs.managed=true"})
            running = sum(1 for c in containers if c.status == "running")
            return running, len(containers)
        except Exception:
            return 0, 0


docker_service = DockerService()
