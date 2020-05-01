# Notebook test runner, adapted from
# https://www.blog.pythonlibrary.org/2018/10/16/testing-jupyter-notebooks/
import nbformat
import os

from nbconvert.preprocessors import ExecutePreprocessor

def hours(hours):
    """ Hours as seconds """
    hours * 60 * 60

def run_notebook(notebook_path, timeout=hours(6), save_nb_path=None):
    nb_name, _ = os.path.splitext(os.path.basename(notebook_path))
    dirname = os.path.dirname(notebook_path)

    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    proc = ExecutePreprocessor(timeout=timeout, kernel_name='python3')
    proc.allow_errors = True

    proc.preprocess(nb, {'metadata': {'path': dirname}})

    if save_nb_path:
        with open(save_nb_path, mode='wt') as f:
            nbformat.write(nb, f)

    errors = []
    for cell in nb.cells:
        if 'outputs' in cell:
            for output in cell['outputs']:
                if output.output_type == 'error':
                    errors.append(output)

    return nb, errors

if __name__ == '__main__':
    nb, errors = run_notebook('Testing.ipynb')
    print(errors)
