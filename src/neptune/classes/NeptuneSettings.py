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
        self.install_path = "/"
        self.continue_on_error = ""
        self.yes_mode = False
        self.no_depend_mode = False
        self.stream_chunk_size = 8192
        self.repositories = {}
        self.lib_dir = f"{self.install_path}/var/lib/neptune/"
        self.cache_dir = f"{self.install_path}/var/lib/neptune/cache"

