# Standard library
import json
import os
import shutil
import subprocess
import sys
import time
from glob import glob

# Packages
from dotenv import load_dotenv
from gemfileparser import GemfileParser
from termcolor import cprint

# Local
from canonicalwebteam.dotrun.file_helpers import file_md5


class State:
    def __init__(self, filepath):
        """
        Manage a JSON object in a file,
        as you would a dictionary
        """

        self.filepath = filepath

    def __getitem__(self, key):
        if not os.path.isfile(self.filepath):
            return None

        with open(self.filepath) as state_file:
            return json.load(state_file).get(key)

    def __setitem__(self, key, value):
        if os.path.isfile(self.filepath):
            with open(self.filepath) as state_file:
                state = json.load(state_file)
        else:
            state = {}

        state[key] = value

        with open(self.filepath, "w") as state_file:
            return json.dump(state, state_file)


class Project:
    """
    A class for performing operations on a project directory
    """

    def __init__(self, path, env_extra):
        self.path = path
        self.statefile_path = f"{self.path}/.dotrun.json"
        self.state = State(self.statefile_path)
        self.env_extra = {}
        self.pyenv_path = f"{self.path}/.venv"

        # Check all env values are string format
        for key, value in env_extra.items():
            self.env_extra[key] = str(value)

        if not os.path.isfile(os.path.join(f"{self.path}/package.json")):
            print(f"ERROR: package.json not found in {self.path}")
            sys.exit(1)

    def install(self, force=False):
        """
        Install dependencies from requirements.txt and package.json,
        if there have been any changes detected
        """

        if os.path.isfile(os.path.join(self.path, "requirements.txt")):
            self._install_python_dependencies(force=force)

        if os.path.isfile(os.path.join(self.path, "Gemfile")):
            self._install_ruby_dependencies(force=force)

        self._install_yarn_dependencies(force=force)

    def clean(self):
        """
        Clean all dotrun data from project
        """

        self._call(
            ["yarn", "--no-default-rc", "run", "clean"], exit_on_error=False
        )

        if os.path.isfile(self.statefile_path):
            cprint(f"[ Removing `{self.statefile_path}` ]", "cyan")
            os.remove(self.statefile_path)

        if os.path.isdir("node_modules"):
            cprint(f"[ Removing node dependencies (`node_modules`) ]", "cyan")
            shutil.rmtree("node_modules")

        if os.path.isdir(self.pyenv_path):
            cprint(
                f"[ Removing python environment (`{self.pyenv_path}`) ]",
                "cyan",
            )
            shutil.rmtree(self.pyenv_path)

    def exec(self, command):
        """
        Run a command in the environment
        """

        self._call(command)

    # Private functions
    # ===

    def _call(self, commands, exit_on_error=True):
        """
        Run a command within the python environment. Optionally run another
        command in the background. The background command will be
        terminated when the foreground command terminates.
        """

        result = None
        load_dotenv(dotenv_path=f"{self.path}/.env")
        load_dotenv(dotenv_path=f"{self.path}/.env.local")
        env = os.environ
        env.update(self.env_extra)

        if os.path.isfile(f"{self.pyenv_path}/bin/python3"):
            cprint(f"[ Using environment at {self.pyenv_path} ]", "cyan")
            env["VIRTUAL_ENV"] = self.pyenv_path
            env["PATH"] = self.pyenv_path + "/bin:" + env["PATH"]
            env.pop("PYTHONHOME", None)

        if os.path.isfile(f"{self.path}/Gemfile"):
            env["BUNDLE_PATH"] = "vendor"

        try:
            cprint(f"\n[ $ {' '.join(commands)} ]\n", "cyan")

            result = subprocess.check_call(commands, env=env, cwd=self.path)
        except KeyboardInterrupt:
            cprint(
                f"\n\n[ `{' '.join(commands)}` cancelled - exiting ]", "cyan"
            )
            time.sleep(1)
        except subprocess.CalledProcessError:
            cprint(
                f"\n[ `{' '.join(commands)}` exited with an error status ]",
                "red",
            )

            if exit_on_error:
                sys.exit(1)

        print("")

        return result

    # Node dependencies

    def _get_installed_yarn_packages(self):
        """
        Inspect "node_modules" to list all packages and versions
        """

        package_jsons = glob(f"{self.path}node_modules/*/package.json")
        packages = {}

        for package_json in package_jsons:
            with open(package_json, "r") as package_contents:
                package = json.load(package_contents)
                packages[package["name"]] = package["version"]

        return packages

    def _install_yarn_dependencies(self, force=False):
        """
        Install yarn dependencies if anything has changed
        """

        changes = False
        lock_path = os.path.join(self.path, "yarn.lock")
        yarn_state = {}

        if os.path.isfile(lock_path):
            yarn_state["lock_hash"] = file_md5(lock_path)

        with open(
            os.path.join(self.path, "package.json"), "rb"
        ) as package_json:
            package_settings = json.load(package_json)
            yarn_state["dependencies"] = package_settings.get(
                "dependencies", {}
            )
            yarn_state["dependencies"].update(
                package_settings.get("devDependencies", {})
            )

        if not force:
            cprint(
                "- Checking dependencies in package.json ... ",
                "magenta",
                end="",
            )

            yarn_state["packages"] = self._get_installed_yarn_packages()

            if self.state["yarn"] == yarn_state:
                cprint("up to date", "magenta")
            else:
                cprint("changes detected", "magenta")
                changes = True
        else:
            cprint(
                "- Installing dependencies from package.json (forced)",
                "magenta",
            )

        if force or changes:
            self._call(["yarn", "--no-default-rc", "install"])
            yarn_state["packages"] = self._get_installed_yarn_packages()
            yarn_state["lock_hash"] = file_md5(lock_path)
            self.state["yarn"] = yarn_state

    # Python dependencies

    def _get_installed_python_packages(self):
        """
        Inspect the "site-packages" folder in the environment to
        list all eggs and wheels
        """

        package_dirs = glob(
            f"{self.pyenv_path}/lib/python*/site-packages/*.*-info"
        )

        return [os.path.basename(path) for path in package_dirs]

    def _install_python_dependencies(self, force=False):
        """
        Install python dependencies if anything has changed
        """

        changes = False
        previous_revision = None
        snap_revision = os.environ.get("SNAP_REVISION")
        if self.state["python"]:
            previous_revision = self.state["python"].get("snap_revision")
        new_snap = previous_revision != snap_revision

        if os.path.isdir(self.pyenv_path) and new_snap:
            # Snap location changes for each new version
            # If snap location has changed it will break the old .venv
            cprint(
                (
                    f"- New dotrun revision {snap_revision} - "
                    "deleting old python environment"
                ),
                "magenta",
            )
            self._call(["rm", "-rf", self.pyenv_path])
            force = True

        if not os.path.isdir(self.pyenv_path) or new_snap:
            cprint("- Creating python environment", "magenta", end="")
            self._call(["virtualenv", self.pyenv_path])
            cprint("done", "magenta")

        python_state = {"snap_revision": snap_revision}

        with open(f"{self.path}/requirements.txt", "r") as requirements_file:
            cprint("- Reading requirements.txt", "magenta")
            python_state["requirements"] = requirements_file.read()

        if not force:
            cprint(
                f"- Checking dependencies in {self.pyenv_path} ... ",
                "magenta",
                end="",
            )

            python_state["packages"] = self._get_installed_python_packages()

            if self.state["python"] == python_state:
                cprint("up to date", "magenta")
            else:
                changes = True
                cprint("changes detected, installing", "magenta")
        else:
            cprint(
                "- Installing dependencies from requirements.txt (forced)",
                "magenta",
            )

        if force or changes:
            self._call(
                ["pip3", "install", "--requirement", "requirements.txt"]
            )
            self._call(["pip3", "install", "ipdb"])
            python_state["packages"] = self._get_installed_python_packages()
            self.state["python"] = python_state

    # Ruby dependencies

    def _get_installed_gems(self):
        """
        Inspect the "vendor" folder in the environment to
        list all gems
        """

        package_dirs = glob(f"{self.path}/vendor/ruby/*/gems/*")

        return [os.path.basename(path) for path in package_dirs]

    def _install_ruby_dependencies(self, force=False):
        """
        If a Gemfile is present, check bundler dependencies
        """

        changes = False
        lock_path = os.path.join(self.path, "Gemfile.lock")
        ruby_state = {}

        if os.path.isfile(lock_path):
            ruby_state["lock_hash"] = file_md5(lock_path)

        ruby_state["dependencies"] = []

        gems = GemfileParser(
            os.path.join(self.path, "Gemfile")
        ).parse()

        for gem in gems["runtime"]:
            ruby_state["dependencies"].append(
                {"name": gem.name, "version": gem.requirement}
            )

        if not force:
            cprint(
                "- Checking dependencies in Gemfile ... ", "magenta", end=""
            )

            ruby_state["gems"] = self._get_installed_gems()

            if self.state["ruby"] == ruby_state:
                cprint("up to date", "magenta")
            else:
                cprint("changes detected", "magenta")
                changes = True
        else:
            cprint(
                "- Installing dependencies from package.json (forced)",
                "magenta",
            )

        if force or changes:
            self._call(["bundle", "install"])
            ruby_state["gems"] = self._get_installed_gems()
            ruby_state["lock_hash"] = file_md5(lock_path)
            self.state["ruby"] = ruby_state
