import sys
from neptune.classes.System import System


class Frontend:
    """
    The direct programs run by users
    """

    def __init__(self, system: System):
        self.system: System = system

    def install(self):
        packages = set(self.system.settings.arguments)
        if not len(packages) > 0:
            print("Usage: neptune-install {{PACKAGES}}")
            sys.exit(1)
        if not self.system.utils.check_if_packages_exist(packages):
            print("Packages not found")
            sys.exit(1)
        print("Getting dependencies")
        packages_to_install = self.system.utils.get_depends(
            packages,
            system_packages=self.system.system_packages,
        )
        if len(packages_to_install) == 0:
            print("Nothing to do all packages are installed")
            sys.exit()
        if not self.system.settings.yes_mode:
            print(
                f"Packages to install: {" ".join([pkg.name for pkg in packages_to_install])}"
            )
            confirmation = input(
                f"{len(packages_to_install)} packages are queued to install, would you like to continue? [Y/n] "
            )
            if not (confirmation == "y" or confirmation == "" or confirmation == "Y"):
                print("Aborting")
                sys.exit(0)
        self.system.install_packages(set(packages_to_install))
        for package in packages:
            self.system.system_packages[package].wanted = True

    def reinstall(self):
        arguments = self.system.settings.arguments
        if not len(arguments) > 0:
            print("Usage: neptune-reinstall {{PACKAGES}}")
            sys.exit(1)
        for package in arguments:
            if package not in self.system.system_packages.keys():
                print(f"{package} is not installed!")
                sys.exit(1)
        if not self.system.settings.yes_mode:
            print(f"Packages to be reinstall: {" ".join(arguments)}")
            confirmation = input(
                f"{len(arguments)} packages are queued to install, would you like to continue? [Y/n] "
            )
            if not (confirmation == "y" or confirmation == "" or confirmation == "Y"):
                print("Aborting")
                sys.exit(0)
        packages = [self.system.system_packages[pkg] for pkg in arguments]
        self.system.install_packages(set(packages))

    def update(self):
        updates = self.system.utils.check_for_updates(
            system_packages=self.system.system_packages
        )
        recalculated_depends = self.system.utils.recalculate_system_depends(
            system_packages=self.system.system_packages
        )
        install = recalculated_depends[0]
        remove = recalculated_depends[1]

        if len(updates) == 0:
            print("No updates found, try to sync")
            sys.exit(0)
        if not self.system.settings.yes_mode:
            print(f"Packages to be updated: {" ".join([pkg.name for pkg in updates])}")
            if len(install) > 0:
                print(
                    f'Packages to be installed: {" ".join([pkg.name for pkg in install])}'
                )
            if len(remove) > 0:
                print(f'Packages to be REMOVED: {" ".join(remove)}')
            confirmation = input("Would you like to continue? [Y/n] ")
            if not (confirmation == "y" or confirmation == "" or confirmation == "Y"):
                print("Aborting")
                sys.exit(0)
        self.system.install_packages(set(updates + install))
        if len(remove) > 0:
            self.system.remove_packages(remove)

    def remove(self):
        if not len(self.system.settings.arguments) > 0:
            print("Usage: neptune remove {{PACKAGES}}")
            sys.exit(1)
        package_names_user_wants_removed: list[str] = self.system.settings.arguments
        for package_name in package_names_user_wants_removed:
            if package_name not in self.system.system_packages.keys():
                print(f"{package_name} is not installed")
                sys.exit(1)
            if not self.system.system_packages[package_name].wanted:
                print(
                    f"{package_name} was installed as a dependency of another package, it can not be removed sanely"
                )
                sys.exit(1)
        system_packages_without_the_ones_to_remove = dict(self.system.system_packages)
        for package_name in package_names_user_wants_removed:
            system_packages_without_the_ones_to_remove.pop(package_name)
        
        absolute_packages_to_remove: list[str] = (
            self.system.utils.recalculate_system_depends(
                system_packages=system_packages_without_the_ones_to_remove,
            )[1] + package_names_user_wants_removed
        )

        if not self.system.settings.yes_mode:
            print(f"Packages to be removed: {" ".join(absolute_packages_to_remove)}")
            confirmation = input(
                f"{len(absolute_packages_to_remove)} packages are queued to remove, would you like to continue? [Y/n] "
            )
            if not (confirmation == "y" or confirmation == "" or confirmation == "Y"):
                print("Aborting")
                sys.exit(0)

        self.system.remove_packages(absolute_packages_to_remove)

    def sync(self):
        for _, repo in self.system.settings.repositories.items():
            repo.sync()
