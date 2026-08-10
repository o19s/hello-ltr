"""
Unit tests for container management utilities.

These focus on the image-staleness guarantees from issue #110: the harness must
never run notebooks against an engine image that the Dockerfile has superseded,
because that failure is silent - the suite goes green and green reads as "the
new version works".
"""

import subprocess
from contextlib import AbstractContextManager
from unittest.mock import patch

import pytest

from tests.fixtures.container_management import (
    find_stale_containers,
    manage_docker_compose,
)


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    """Build a CompletedProcess stand-in for a mocked subprocess.run call."""
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=""
    )


class TestManageDockerComposeBuildFlag:
    """The `up` path must force Docker to re-evaluate `build:` directives."""

    def _run_action(self, action: str) -> list[str]:
        """Invoke manage_docker_compose and return the command it would run."""
        with (
            patch(
                "tests.fixtures.container_management.get_docker_compose_cmd",
                return_value="docker compose",
            ),
            patch(
                "tests.fixtures.container_management.subprocess.run",
                return_value=_completed(),
            ) as mock_run,
        ):
            manage_docker_compose(
                "opensearch", action, project_name="test-notebooks-opensearch-gw0"
            )
        return mock_run.call_args[0][0]

    def test_up_passes_build(self):
        """Without --build, a changed Dockerfile is silently ignored (issue #110)."""
        cmd = self._run_action("up")
        assert "--build" in cmd

    def test_up_still_detached(self):
        """--build must not displace the existing detached-mode behaviour."""
        cmd = self._run_action("up")
        assert "-d" in cmd

    def test_build_action_supported(self):
        """The fixture builds explicitly before deciding whether to reuse containers."""
        cmd = self._run_action("build")
        assert cmd[-1] == "build"

    def test_down_does_not_pass_build(self):
        """--build is meaningless on teardown and must not leak into it."""
        cmd = self._run_action("down")
        assert "--build" not in cmd
        assert "-v" in cmd

    def test_ps_does_not_pass_build(self):
        """A status query must stay side-effect free."""
        cmd = self._run_action("ps")
        assert "--build" not in cmd


class TestFindStaleContainers:
    """Detecting containers left running on an image the build has superseded."""

    def _patch_docker(
        self, ps_output: str, inspect_map: dict
    ) -> AbstractContextManager:
        """
        Fake `docker ps` and `docker inspect`.

        inspect_map maps (target, format) to the string docker would print, or
        None to simulate a target that does not exist.
        """

        def fake_run(cmd, **kwargs):
            if cmd[1] == "ps":
                return _completed(ps_output)
            # docker inspect --format <fmt> <target>
            fmt, target = cmd[3], cmd[4]
            value = inspect_map.get((target, fmt))
            if value is None:
                return _completed(returncode=1)
            return _completed(value)

        return patch(
            "tests.fixtures.container_management.subprocess.run", side_effect=fake_run
        )

    IMAGE_FMT = "{{.Image}}"
    SERVICE_FMT = '{{index .Config.Labels "com.docker.compose.service"}}'
    ID_FMT = "{{.Id}}"

    def test_detects_container_on_superseded_image(self):
        """The exact issue #110 scenario: container predates the current build."""
        with self._patch_docker(
            "proj-opensearch-node1-1\n",
            {
                ("proj-opensearch-node1-1", self.IMAGE_FMT): "sha256:old",
                ("proj-opensearch-node1-1", self.SERVICE_FMT): "opensearch-node1",
                ("proj-opensearch-node1", self.ID_FMT): "sha256:new",
            },
        ):
            assert find_stale_containers("proj") == ["proj-opensearch-node1-1"]

    def test_current_container_is_not_stale(self):
        """A container already on the freshly built image must be left alone."""
        with self._patch_docker(
            "proj-opensearch-node1-1\n",
            {
                ("proj-opensearch-node1-1", self.IMAGE_FMT): "sha256:same",
                ("proj-opensearch-node1-1", self.SERVICE_FMT): "opensearch-node1",
                ("proj-opensearch-node1", self.ID_FMT): "sha256:same",
            },
        ):
            assert find_stale_containers("proj") == []

    def test_service_without_built_image_is_skipped(self):
        """
        A service declared with `image:` has no <project>-<service> tag.

        It cannot go stale from a Dockerfile edit, so a missing tag must not be
        read as "stale" - that would tear down healthy containers every run.
        """
        with self._patch_docker(
            "proj-kibana-1\n",
            {
                ("proj-kibana-1", self.IMAGE_FMT): "sha256:pulled",
                ("proj-kibana-1", self.SERVICE_FMT): "kibana",
                # no ("proj-kibana", ID_FMT) entry - image was pulled, not built
            },
        ):
            assert find_stale_containers("proj") == []

    def test_reports_only_the_stale_container(self):
        """Mixed projects: recreate only what is actually out of date."""
        with self._patch_docker(
            "proj-opensearch-node1-1\nproj-dashboards-1\n",
            {
                ("proj-opensearch-node1-1", self.IMAGE_FMT): "sha256:old",
                ("proj-opensearch-node1-1", self.SERVICE_FMT): "opensearch-node1",
                ("proj-opensearch-node1", self.ID_FMT): "sha256:new",
                ("proj-dashboards-1", self.IMAGE_FMT): "sha256:same",
                ("proj-dashboards-1", self.SERVICE_FMT): "dashboards",
                ("proj-dashboards", self.ID_FMT): "sha256:same",
            },
        ):
            assert find_stale_containers("proj") == ["proj-opensearch-node1-1"]

    def test_no_running_containers(self):
        """Nothing running means nothing to recreate."""
        with self._patch_docker("", {}):
            assert find_stale_containers("proj") == []

    def test_docker_ps_failure_fails_open(self):
        """Staleness detection must never be the reason a run cannot start."""
        with patch(
            "tests.fixtures.container_management.subprocess.run",
            return_value=_completed(returncode=1),
        ):
            assert find_stale_containers("proj") == []

    def test_docker_unavailable_fails_open(self):
        """A missing docker binary must raise nothing from this helper."""
        with patch(
            "tests.fixtures.container_management.subprocess.run",
            side_effect=OSError("docker not found"),
        ):
            assert find_stale_containers("proj") == []

    def test_docker_timeout_fails_open(self):
        """A hung docker daemon must not hang or crash collection."""
        with patch(
            "tests.fixtures.container_management.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=10),
        ):
            assert find_stale_containers("proj") == []

    def test_filters_by_compose_project_label(self):
        """
        Containers are selected by compose project label, not by name matching.

        Name matching would sweep in unrelated projects that share a prefix.
        """
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _completed("")

        with patch(
            "tests.fixtures.container_management.subprocess.run", side_effect=fake_run
        ):
            find_stale_containers("test-notebooks-opensearch-gw0")

        assert (
            "label=com.docker.compose.project=test-notebooks-opensearch-gw0"
            in captured["cmd"]
        )


class TestManageDockerComposeSafety:
    """The existing project-name guard must survive these changes."""

    def test_rejects_non_test_project_name(self):
        """Never operate on manually started containers."""
        with (
            patch(
                "tests.fixtures.container_management.get_docker_compose_cmd",
                return_value="docker compose",
            ),
            pytest.raises(RuntimeError, match="CRITICAL SAFETY VIOLATION"),
        ):
            manage_docker_compose("opensearch", "up", project_name="opensearch")
