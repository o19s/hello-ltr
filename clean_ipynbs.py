import nbclean as nbc
import os

if __name__ == "__main__":
    for fname in os.listdir('.'):
        if fname.endswith('.ipynb'):
            print("cleaning %s" % fname)
            ntbk = nbc.NotebookCleaner(fname)
            ntbk.clear(kind='output', tag='hide_output')
            ntbk.clear(kind='outputs', tag='hide_output')
            ntbk.save(fname)
