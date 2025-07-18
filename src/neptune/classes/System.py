from dataclasses import asdict
import logging
import os
import shutil
import subprocess
import sys
from typing import Any

from rich.console import Console, Group
from rich.status import Status
from rich.live import Live
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Column
import yaml
from neptune.classes.Package import Package
from neptune.classes.NeptuneSettings import NeptuneSettings
from neptune.classes.Utils import Utils


class System:
    """
    General rule of thumb is that all functions that can modify the
    system live here. Other than that functions that virtually can't
    work without the system being initalized are also in this class
    """

    def __init__(self, settings: NeptuneSettings):
        self.settings: NeptuneSettings = settings
        self.postinstalls: list[str] = []
        self.utils: Utils = Utils(self.settings)
        try:
            with open(f"{self.settings.lib_dir}/system-packages.yaml", "r") as f:
                try:
                    raw_data: dict[str, dict[str, Any]] = yaml.load(f, Loader=yaml.CSafeLoader)
                    if raw_data is None: # type: ignore -- yaml.safe_load doesn't care about the annotation and will make it None anyways
                        raw_data={}
                        
                    self.system_packages: dict[str, Package] = {
                        name: Package(**metadata, name=name)
                        for name, metadata in raw_data.items()
                    }
                except Exception as e:
                    logging.critical(f"YAML syntax error: {e}")
                    sys.exit(1)
        except OSError as e:
            logging.critical(f"Could not open file: {e}")
            sys.exit(1)

    def postinst(self):
        for package in self.postinstalls:
            print(f"Running {package} post-install")
            subprocess.run(f"bash /tmp/{package}-postinst", shell=True)
            subprocess.run(f"rm -f /tmp/{package}-postinst", shell=True)

    def check_for_and_delete(self, path_to_delete: str) -> None:
        # in case more logic is needed later
        subprocess.run(["rm", "-f", path_to_delete])

    def remove_old_files(self, package: str, new_file_list: list[str]) -> None:
        # used for update to remove old stale files
        folder_set : set[str] = set()
        to_remove: list[str] = []
        files_old = set(
            open(f"{self.settings.lib_dir}/file-lists/{package}.list", "r")
            .read()
            .splitlines()
        )
        to_remove += [file for file in files_old if file not in new_file_list]
        logging.debug(f"{package} removal wants to remove files: {to_remove}")
        for file in to_remove:
            self.check_for_and_delete(file)
            folder_set.add(os.path.dirname(file))
            
        for folder in folder_set:
            self.utils.try_remove_folder(folder)
        

    def remove_package(self, package_name: str) -> None:
        # This does NOT do depend checking. This will remove ANY package given to it even if it required for system operation.
        # Use recalculate_system_depends BEFORE using this package
        folder_set : set[str] = set()
        try:
            files = set(
                open(f"{self.settings.lib_dir}/file-lists/{package_name}.list", "r")
                .read()
                .splitlines()
            )
        except FileNotFoundError:
            print(f"File list for {package_name} not found, skipping removal")
            return
        print(f"Removing {package_name}")
        
        for file in files:
            # os/subprocesses remove function will crash the system if it's removing something that is currently in use
            self.check_for_and_delete(f"{self.settings.install_path}/{file}")
            folder_set.add(os.path.dirname(f"{self.settings.install_path}/{file}"))
            
        for folder in folder_set:
            self.utils.try_remove_folder(folder)
            
        self.system_packages.pop(package_name)

    def remove_packages(self, package_names: list[str]):
        text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
        bar_column = BarColumn(bar_width=80, table_column=Column(ratio=5))
        with Progress(text_column, bar_column, expand=True) as progress:
            remove_task = progress.add_task(
                "[red]Removing...", total=len(package_names)
            )
            for package_name in package_names:
                self.remove_package(package_name)
                progress.update(remove_task, advance=1)
                
    def move_with_permissions(self, src_path: str, dest_path: str) -> None:
        dir_name = os.path.dirname(dest_path)
        base_name = os.path.basename(dest_path)
        temp_path = os.path.join(dir_name, f".{base_name}.tmp")

        stat_info = None
        if not os.path.islink(src_path):
            stat_info = os.stat(src_path)

        shutil.copy2(src_path, temp_path, follow_symlinks=False)

        if stat_info is not None:
            os.chown(temp_path, stat_info.st_uid, stat_info.st_gid)
            os.chmod(temp_path, stat_info.st_mode)
        if os.path.exists(dest_path) and (os.path.isdir(src_path) != os.path.isdir(dest_path)):
            shutil.rmtree(dest_path)
        os.replace(temp_path, dest_path)
        os.remove(src_path)
        logging.debug(
            f"Replaced {dest_path} with {src_path} (preserved metadata)."
        )


    def install_files(self, package: str) -> None:
        # needed for updates & reinstalls
        os.chdir(f"{self.settings.cache_dir}/{package}")
        backup = self.utils.parse_backup_file(package)
        logging.debug(
            f"Install Path to install {package} is {self.settings.install_path}"
        )
        for root, dirs, files in os.walk(".", followlinks=False):
            for dir in dirs:
                src_path = os.path.join(root, dir)
                abs_path = os.path.join(root, dir)
                # this is not redundant, os.join will ignore adding the install path if this is absolute
                rel_path = os.path.relpath(abs_path, start=".")
                dest_path = os.path.join(self.settings.install_path, rel_path)
                if os.path.islink(src_path):
                    self.move_with_permissions(src_path, dest_path)
                else:
                    os.makedirs(dest_path, exist_ok=True)
            for file in files:
                src_path = os.path.join(root, file)
                abs_path = os.path.join(root, file)
                # this is not redundant, os.join will ignore adding the install path if this is absolute
                rel_path = os.path.relpath(abs_path, start=".")
                dest_path = os.path.join(self.settings.install_path, rel_path)
                logging.debug(f"Destination path: {dest_path}")
                if dest_path in (
                    self.settings.install_path + "/postinst",
                    "/depends",
                    "/depend",
                    "/make-depend",
                    "/make-depends",
                    "/preinst",
                    "/prerm",
                    "/preupdate",
                    "/backup",
                    "/version",
                ):
                    continue
                if (dest_path not in backup) or (not os.path.exists(dest_path)):
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    self.move_with_permissions(src_path, dest_path)
        os.chdir(self.settings.cache_dir)

    def install_package(
        self,
        package: Package,
        console_line: Status,
    ) -> None:
        if not os.path.exists(self.settings.cache_dir):
            os.makedirs(self.settings.cache_dir)
        os.chdir(self.settings.cache_dir)

        # we can leave the other ones blank since we are using a package
        self.settings.repositories[package.repo].download_link(
            "", "", package=package.name, console_line=console_line
        )

        console_line.update(f"{package.name} Extracting...")
        subprocess.run(["tar", "-xpf", f"{package.name}.tar.xz"])

        logging.info(f"Generating File List for {package.name}")

        file_list = self.utils.generate_file_list(package.name)
        if os.path.isfile(f"{self.settings.lib_dir}/file-lists/{package.name}.list"):
            self.remove_old_files(package.name, file_list)

        open(f"{self.settings.lib_dir}/file-lists/{package.name}.list", "w").write(
            "\n".join(file_list)
        )

        console_line.update(f"{package.name} Installing...")

        if os.path.exists(f"{package.name}/postinst"):
            self.postinstalls.append(package.name)
            subprocess.run(
                ["cp", f"{package.name}/postinst", f"/tmp/{package.name}-postinst"]
            )

        self.install_files(package.name)
        # TODO set wanted might cause keyerror
        if package.name in self.system_packages and self.system_packages[package.name].wanted:
            package.wanted = True
            
        self.system_packages[package.name] = package

        subprocess.run(["rm", "-rf", package.name])
        subprocess.run(["rm", "-f", f"{package.name}.tar.xz"])

    def install_packages(self, packages: set[Package]):
        # This does NOT run get depends before, in order to
        # get the objects needed to pass into this use get_depends
        console = Console()
        text_column = TextColumn("{task.description}", table_column=Column(ratio=1))
        bar_column = BarColumn(bar_width=None, table_column=Column(ratio=5))
        progress = Progress(text_column, bar_column, expand=True)
        status_lines: list[str] = []
        current_line = console.status("", refresh_per_second=10)
        task = progress.add_task("Installing", total=len(packages))
        rows = shutil.get_terminal_size().lines - 4

        def get_status_group():
            visible_lines = (
                status_lines[-rows:] if len(status_lines) > rows else status_lines
            )
            return Group(
                *visible_lines,  # All completed package lines
                current_line,  # Current operation line
                progress,  # Progress bar at bottom
            )

        with Live(get_status_group(), refresh_per_second=10, console=console) as live:

            for package in packages:
                self.install_package(package, console_line=current_line)
                status_lines.append(rf" {package.name} \[[bold blue]✔[/bold blue]]")
                progress.update(task, advance=1)
                live.update(get_status_group())

        # only needed for bootstrap postinst
        if self.settings.run_postinst:
            self.postinst()

    def save_state(self):
        # Convert to serializable dict (no name inside, key is the name)
        packages_as_dict: dict[str, dict[str, Any]] = {
            package_name: {
                k: v for k, v in asdict(package_metadata).items() if k != "name"
            }
            for package_name, package_metadata in self.system_packages.items()
        }

        # Save to YAML
        with open(f"{self.settings.lib_dir}/system-packages.yaml", "w") as f:
            yaml.dump(packages_as_dict, f)
