class NeptuneSettings:
    # I really hate this method but I need a global data class
    _instance = None

    repo = ""
    install_path = ""
    yes_mode = False
    stream_chunk_size = 8192
    # common cheat, if a new instance is created just return the old one
    def __new__(cls):
        if cls._instance is None:
        # I never thought I would say this but it looks better in java then in python
            cls._instance = super(NeptuneSettings, cls).__new__(cls)
        return cls._instance
