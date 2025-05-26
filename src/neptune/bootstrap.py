import logging
import subprocess
import sys
import os
from neptune.classes.Frontend import Frontend
from neptune.classes.NeptuneSettings import NeptuneSettings
from neptune.classes.Package import Package
from neptune.classes.System import System

# This runs completely standalone from __init__ and therefore a lot of functions are repeated
# TODO fix this garbage

if os.geteuid() != 0:
    logging.error("This package manager must be run as root")
    sys.exit()


arguments = list(sys.argv)
arguments.pop(0)
base_settings = NeptuneSettings(arguments)
system = System(base_settings)
frontend = Frontend(system)
settings = system.settings
path = ""


def parse_arguments():
    valid_cli_arguments = ["--y"]

    if len(arguments) == 0:
        usage = """Usage: neptune-bootstrap [path] [flags]
   Flags:
       --y: Temporarily disables confirmation with all operations that require one
           """
        print(usage)
        sys.exit(0)
    global path
    path = arguments[0]
    arguments.pop(0)
    for arg in range(len(valid_cli_arguments)):
        if valid_cli_arguments[arg] in arguments:
            match arg:
                case 0:
                    settings.yes_mode = True
                case 1:
                    settings.no_depend_mode = True
                case _:
                    logging.critical(
                        "Neptune bug could not find argument even though it's valid"
                    )
            # How many packages could you possibly pass? probably fine to use remove
            arguments.remove(valid_cli_arguments[arg])


def create_inital_files():
    os.makedirs(settings.cache_dir)
    os.makedirs(f"{settings.lib_dir}/file-lists")
    os.makedirs(f"{settings.cache_dir}/depend")
    subprocess.run(f"touch {settings.lib_dir}/versions", shell=True)
    subprocess.run(f"touch {settings.lib_dir}/installed_package", shell=True)


def bootstrap():
    settings.parse_config()
    settings.parse_repos()
    parse_arguments()
    settings.install_path = path
    settings.run_postinst = False
    settings.cache_dir = f"{path}/var/lib/neptune/cache"
    settings.lib_dir = f"{path}/var/lib/neptune/"
    if not os.listdir(path) == []:
        print("This directory is not empty!")
        sys.exit(1)
    create_inital_files()
    # This sync would sync the system about to be bootstrapped which isn't advisable.
    frontend.sync()

    print("Getting dependencies")
    packages: list[Package] = system.utils.get_depends(set(["base"]))
    if not settings.yes_mode:
        print(f"Packages to install: {" ".join([pkg.name for pkg in packages])}")
        confirmation = input(
            f"You are about to bootstrap {path}, would you like to continue? [Y/n] "
        )
        if not (confirmation == "y" or confirmation == "" or confirmation == "Y"):
            print("Aborting")
            sys.exit(0)
    system.install_packages(set(packages))
    system.system_packages["base"].wanted = True
    system.save_state()
