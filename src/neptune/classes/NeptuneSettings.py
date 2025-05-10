import logging
import sys
import yaml
from neptune.classes.Repository import Repository


class NeptuneSettings:
    # I really hate this method but I need a global data class
    _instance = None

    # common cheat, if a new instance is created just return the old one
    def __new__(cls):
        if cls._instance is None:
        # I never thought I would say this but it looks better in java then in python
            cls._instance = super(NeptuneSettings, cls).__new__(cls)
            cls._instance.init()
        return cls._instance
    # not true constructor as it would attempt to call it every time then
    def init(self):
        #print("Reinitalizing")
        # TODO Consider removing install_path
        self.arguments : list[str] = sys.argv
        self.install_path = "/"
        self.yes_mode = False
        self.run_postinst = True
        self.no_depend_mode = False
        self.stream_chunk_size = 8192
        self.debug_level = 30
        self.repositories: dict[str, Repository] = {}
        self.lib_dir = f"{self.install_path}/var/lib/neptune/"
        self.cache_dir = f"{self.install_path}/var/lib/neptune/cache"
        self.arguments : list[str] = [] 

    def parse_config(self) -> None:
       try:
          with open('/etc/neptune/config.yaml', 'r') as config_file:
             try:
                config = yaml.safe_load(config_file)
             except yaml.YAMLError as e:
                print(f"Error parsing yaml syntax {e}")
       except Exception as e:
          logging.error(f"An unexpected error occured {e}")
          sys.exit(1)
       try:
          self.install_path = config['system-settings']['install_path']
          self.yes_mode = config['system-settings']['yes_mode_by_default']
          self.stream_chunk_size = config['system-settings']['stream_chunk_size']
          self.debug_level = config['system-settings']['loglevel']
       except KeyError as e:
          logging.error(f"An unexpected value was found in {e}")
          sys.exit(1)

    def parse_repos(self) -> None:
       try:
          with open('/etc/neptune/repositories.yaml', 'r') as repo_file:
             try:
                repos = yaml.safe_load(repo_file)
             except yaml.YAMLError as e:
                logging.error(f"Error parsing yaml syntax {e}")
                sys.exit(1)
       except Exception as e:
          logging.error(f"An unexpected error occured {e}")
          sys.exit(1)
       try:
          for repo_name, repo_data in repos['repositories'].items():
             repo_object = Repository(repo_name, repo_data['url'])
             self.repositories[repo_name] = repo_object
       except Exception as e:
             logging.error(f"Error parsing repositories file exception {e}")

    def parse_arguments(self):
      valid_cli_arguments = ["--y", "--no-depend"]

      if len(self.arguments) == 0 or (self.arguments[0] not in ("install", "update", "sync", "reinstall", "remove")):
         usage="""Usage: neptune [operation] [flags] [packages (if applicable)]
           
    The package manager, used to install, update, reinstall, or remove packages

       Operations:
          sync: Used to sync local cache with the repository, you need to do this before updating
          install: Used to install programs, append any and all packages that you want to install after this
          reinstall: Used to reinstall packages, append any and all packages that you want reinstalled after this
          update: Used to update the system, do NOT append any packages after this
          remove: Used to remove packages from the system
       Flags:
           --y: Temporarily disables confirmation with all operations that require one
           --no-depend: Temporarily disables dependency resolution"""
         print(usage)
         sys.exit(0)
      self.operation = self.arguments[0]
      self.arguments.pop(0)
      for argindex in range(len(valid_cli_arguments)):
        if valid_cli_arguments[argindex] in self.arguments:
          match argindex:
             case 0:
                self.settings.yes_mode = True
             case 1:
                self.settings.no_depend_mode = True
          # How many packages could you possibly pass? probably fine to use remove
          self.arguments.remove(valid_cli_arguments[argindex])