import os
import re
import unittest
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(os.environ.get("ARCHPATH_ROOT", Path(__file__).resolve().parents[1]))


class ScaffoldContractTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        path = ROOT / relative_path
        self.assertTrue(
            path.is_file(), f"Required scaffold file is missing: {relative_path}"
        )
        return path.read_text(encoding="utf-8")

    def test_compose_declares_application_and_test_services(self) -> None:
        compose = self.read("compose.yaml")
        for service in (
            "backend",
            "frontend",
            "backend-tests",
            "frontend-tests",
            "e2e-tests",
        ):
            with self.subTest(service=service):
                self.assertRegex(compose, rf"(?m)^  {re.escape(service)}:\s*$")

        self.assertRegex(compose, r'profiles:\s*(?:\[\s*"test"\s*\]|-\s*test)')
        self.assertNotRegex(
            compose,
            r"(?m)^  (database|db|postgres|redis|broker|rabbitmq|kafka):\s*$",
        )
        self.assertNotIn("/var/run/docker.sock", compose)

    def test_compose_publishes_ports_only_on_loopback(self) -> None:
        compose = self.read("compose.yaml")
        self.assertRegex(compose, r"127\.0\.0\.1:8000:8000")
        self.assertRegex(compose, r"127\.0\.0\.1:5173:5173")

    def test_backend_is_pinned_to_one_worker_and_has_readiness_probe(self) -> None:
        compose = self.read("compose.yaml")
        backend = re.search(
            r"(?ms)^  backend:\s*\n(?P<body>.*?)(?=^  [\w-]+:\s*$|\Z)",
            compose,
        )
        self.assertIsNotNone(backend, "backend service was not found")
        assert backend is not None
        self.assertIn("--workers", backend["body"])
        self.assertIn("1", backend["body"])
        self.assertIn("healthcheck:", backend["body"])
        self.assertIn("/healthz", backend["body"])
        self.assertNotRegex(backend["body"], r"(?m)^\s+volumes:\s*$")

    def test_frontend_proxy_targets_backend_service(self) -> None:
        config = self.read("frontend/vite.config.ts")
        self.assertIn('"/api"', config)
        self.assertIn("http://backend:8000", config)

    def test_dependency_manifests_and_lockfiles_are_present(self) -> None:
        self.read("backend/pyproject.toml")
        self.read("backend/uv.lock")
        self.read("frontend/package.json")
        self.read("frontend/package-lock.json")

    def test_environment_files_are_ignored_except_example(self) -> None:
        gitignore = self.read(".gitignore")
        self.assertIn(".env", gitignore)
        self.assertIn("!.env.example", gitignore)

    def test_backend_health_endpoint_is_reachable_when_configured(self) -> None:
        base_url = os.environ.get("BACKEND_BASE_URL")
        if not base_url:
            self.skipTest(
                "BACKEND_BASE_URL is set only in the Compose integration-test service"
            )

        try:
            with urlopen(f"{base_url.rstrip('/')}/healthz", timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(
                    "application/json", response.headers.get("Content-Type", "")
                )
        except URLError as error:
            self.fail(f"Backend health endpoint is not reachable: {error}")

    def test_frontend_is_reachable_when_configured(self) -> None:
        base_url = os.environ.get("FRONTEND_BASE_URL")
        if not base_url:
            self.skipTest(
                "FRONTEND_BASE_URL is set only in the Compose integration-test service"
            )

        try:
            with urlopen(base_url.rstrip("/") + "/", timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("text/html", response.headers.get("Content-Type", ""))
                self.assertIn(
                    "<title>ArchPath</title>", response.read().decode("utf-8")
                )
        except URLError as error:
            self.fail(f"Frontend is not reachable: {error}")

    def test_compose_regression_script_runs_all_suites_sequentially(self) -> None:
        script = self.read("scripts/test-compose.sh")
        commands = [
            "docker compose --profile test run --build --rm backend-tests",
            "docker compose restart backend",
            "CHECK_AFTER_BACKEND_RESTART=1",
            "docker compose --profile test run --build --rm frontend-tests",
            "docker compose --profile test run --build --rm e2e-tests",
        ]
        positions = [script.index(command) for command in commands]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("trap cleanup EXIT", script)
        self.assertIn("docker compose --profile test rm -sf", script)

    def test_ci_runs_static_checks_and_repeats_compose_regression(self) -> None:
        workflow = self.read(".github/workflows/ci.yml")
        self.assertIn("  push:", workflow)
        self.assertIn("  pull_request:", workflow)
        self.assertIn("docker compose config --quiet", workflow)
        self.assertIn("ruff check app tests && ruff format --check app tests", workflow)
        self.assertIn("npm run lint && npm run build", workflow)
        self.assertGreaterEqual(workflow.count("sh scripts/test-compose.sh"), 2)
        self.assertIn("docker compose down --remove-orphans", workflow)

    def test_e2e_container_pins_playwright_and_waits_for_app_readiness(self) -> None:
        dockerfile = self.read("frontend/Dockerfile.e2e")
        self.assertRegex(
            dockerfile,
            r"(?m)^FROM mcr\.microsoft\.com/playwright:v[\d.]+-noble$",
        )
        self.assertIn("RUN npm ci", dockerfile)
        self.assertIn("USER pwuser", dockerfile)

        compose = self.read("compose.yaml")
        e2e_service = re.search(
            r"(?ms)^  e2e-tests:\s*\n(?P<body>.*?)(?=^  [\w-]+:\s*$|\Z)",
            compose,
        )
        self.assertIsNotNone(e2e_service, "e2e-tests service was not found")
        assert e2e_service is not None
        self.assertIn("condition: service_healthy", e2e_service["body"])
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH", e2e_service["body"])

    def test_sse_endpoint_is_available_and_keeps_an_empty_stream_open(self) -> None:
        base_url = os.environ.get("BACKEND_BASE_URL")
        if not base_url:
            self.skipTest(
                "BACKEND_BASE_URL is set only in the Compose integration-test service"
            )

        try:
            with urlopen(
                f"{base_url.rstrip('/')}/api/simulacao/eventos", timeout=3
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    response.headers.get("Content-Type", "").split(";", maxsplit=1)[0],
                    "text/event-stream",
                )
        except URLError as error:
            self.fail(f"SSE endpoint is not reachable: {error}")


if __name__ == "__main__":
    unittest.main()
