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
        self.repo = ""
        self.install_path = ""
        self.yes_mode = False
        self.no_depend_mode = False
        self.stream_chunk_size = 8192
