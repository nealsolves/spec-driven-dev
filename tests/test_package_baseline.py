import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

from tests.helpers import ROOT


class PackageBaselineTest(unittest.TestCase):
    def build_wheel(self, temporary_root: Path) -> Path:
        wheel_directory = temporary_root / "wheel"
        build = subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--no-isolation",
                "--outdir",
                str(wheel_directory),
                str(ROOT),
            ],
            cwd=temporary_root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        wheels = list(wheel_directory.glob("*.whl"))
        self.assertEqual(len(wheels), 1, wheels)
        return wheels[0]

    def test_built_wheel_installs_with_one_authoritative_version(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            wheel = self.build_wheel(temporary_root)
            install_directory = temporary_root / "installed"
            install = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-compile",
                    "--no-deps",
                    "--target",
                    str(install_directory),
                    str(wheel),
                ],
                cwd=temporary_root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)

            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(install_directory)
            probe = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import json; from importlib.metadata import version; "
                    "import sdd; print(json.dumps({'distribution': "
                    "version('spec-driven-dev'), 'module': sdd.__version__}, "
                    "sort_keys=True))",
                ],
                cwd=temporary_root,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(probe.returncode, 0, probe.stdout + probe.stderr)
            versions = json.loads(probe.stdout)
            self.assertEqual(versions["module"], versions["distribution"])
            self.assertEqual(str(Version(versions["module"])), versions["module"])

    def test_built_wheel_declares_supported_runtime_and_policy_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            wheel = self.build_wheel(Path(directory))
            with zipfile.ZipFile(wheel) as archive:
                metadata_files = [
                    name
                    for name in archive.namelist()
                    if name.endswith(".dist-info/METADATA")
                ]
                self.assertEqual(len(metadata_files), 1, metadata_files)
                metadata = BytesParser().parsebytes(archive.read(metadata_files[0]))

            self.assertEqual(metadata["Requires-Python"], ">=3.11")
            requirements = {
                canonicalize_name(requirement.name): str(requirement.specifier)
                for requirement in map(Requirement, metadata.get_all("Requires-Dist", []))
            }
            self.assertEqual(
                requirements,
                {
                    "jsonschema": "<5,>=4.23",
                    "pyyaml": "<7,>=6.0",
                },
            )


if __name__ == "__main__":
    unittest.main()
