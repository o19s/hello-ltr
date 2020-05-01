import os

class NotebookTestConfig:

    SETUP_NB = 'setup.ipynb'

    def __init__(self, path):
        self.notebooks = []
        self.setup = None
        for nb_path in os.listdir(path):
            full_nb_path = os.path.join(path,nb_path)
            if os.path.isfile(full_nb_path) and nb_path.endswith('.ipynb'):
                if nb_path == NotebookTestConfig.SETUP_NB:
                    self.setup = full_nb_path
                else:
                    self.notebooks.append(full_nb_path)

