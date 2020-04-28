import nbformat
import os

from nbconvert.preprocessors import ExecutePreprocessor


def run_notebook(notebook_path):
    nb_name, _ = os.path.splitext(os.path.basename(notebook_path))
    dirname = os.path.dirname(notebook_path)

    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    proc = ExecutePreprocessor(timeout=600, kernel_name='python3')
    proc.allow_errors = True

    proc.preprocess(nb, {'metadata': {'path': dirname}})

    #output_path = os.path.join('.', '{}_all_output.ipynb'.format(nb_name))

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
