"""Execute the student notebook in a fresh kernel and protect existing research/user files.

From Program:
uv run --project experiments/walkthrough_v1 --locked python.exe -X utf8 -B notebooks/verify_walkthrough.py
"""
import hashlib
import json
import os
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
import sys

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / 'notebooks/01_understand_your_fyp.ipynb'
OUT = ROOT / 'reports/2026-10-16/walkthrough_v1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(paths):
    return {p.relative_to(ROOT).as_posix(): (sha(p), p.stat().st_mtime_ns) for p in sorted(paths)}


def main():
    paths = {ROOT / 'uv.lock', ROOT / 'pyproject.toml', ROOT / 'reports/FYP_v1.docx',
             ROOT / 'experiments/model_dev_v1/uv.lock', ROOT / 'experiments/model_dev_v1/pyproject.toml'}
    for base in ['src', 'config', 'data/application', 'data/processed/powerbi_v1', 'reports/powerbi']:
        paths.update(p for p in (ROOT / base).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for relative in ['reports/2026-10-06/analysis_v1/manifest.json',
        'reports/2026-10-07/model_dev_v1/run_manifest.json', 'reports/2026-10-10/model_tree_v1/run_manifest.json',
        'reports/2026-10-11/model_age_v1/run_manifest.json', 'reports/2026-10-13/model_scope_v1/run_manifest.json']:
        path = ROOT / relative
        paths.add(path)
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if 'artifacts' in manifest:
            paths.update(ROOT / name for name in manifest['artifacts'])
            paths.update(path.parent / name for name in manifest['outputs'])
        else:
            paths.update(ROOT / name for name in manifest['outputs'])
    before = snapshot(paths)
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    # Explicitly select the isolated environment's kernel, never a user's global kernel.
    manager = KernelManager(kernel_name='python3', kernel_spec_manager=KernelSpecManager(
        kernel_dirs=[str(Path(sys.prefix) / 'share/jupyter/kernels')]))
    client = NotebookClient(notebook, timeout=300, km=manager, resources={'metadata': {'path': str(ROOT)}},
                            allow_errors=False, record_timing=False)
    print('Executing walkthrough with a fresh isolated kernel...', flush=True)
    # Helper code imports are read-only; suppress optional .pyc creation too.
    client.execute(cleanup_kc=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'})
    after = snapshot(paths)
    assert before == after, 'A protected input/research/user file changed'
    code_cells = [c for c in notebook.cells if c.cell_type == 'code']
    assert all(c.execution_count is not None for c in code_cells)
    assert not any(o.output_type == 'error' for c in code_cells for o in c.outputs)
    images = sum('image/png' in o.get('data', {}) for c in code_cells for o in c.outputs)
    assert images == 3, f'Expected three inline plots, found {images}'
    summary = json.loads((OUT / 'execution_summary.json').read_text())
    assert summary['csv_rows'] == 221806 and summary['fit_rows'] == 147902 and summary['validation_rows'] == 73904
    assert summary['developer_group_overlap'] == 0 and summary['max_probability_difference'] < 1e-10
    assert not summary['calibration_evaluated'] and not summary['test_evaluated']
    nbformat.write(notebook, NOTEBOOK)
    result = {'status': 'passed', 'date': '2026-10-16', 'executed_code_cells': len(code_cells),
        'inline_plots': images, 'protected_files_unchanged': len(before), 'sha256_and_mtime_preserved': True,
        'notebook_sha256': sha(NOTEBOOK), 'environment_lock_sha256': sha(ROOT / 'experiments/walkthrough_v1/uv.lock'),
        'execution_summary_sha256': sha(OUT / 'execution_summary.json'),
        'verifier_sha256': sha(Path(__file__)), 'calibration_evaluated': False, 'test_evaluated': False,
        'ui_launch_tested': False, 'checks': ['fresh-kernel sequential execution', 'three inline and exported figures',
        'CSV counts and labels agree with frozen train', 'developer groups are disjoint',
        'new predictions reproduce existing fold OOF', 'existing research/app/DOCX/Power BI files unchanged']}
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
