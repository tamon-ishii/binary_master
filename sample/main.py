"""Central sample runner for binary_master.

Executes all numbered Jupyter notebook samples systematically:
1. sample/01_basic_struct.ipynb
2. sample/02_bitfields_and_alignment.ipynb
3. sample/03_offsets_and_tables.ipynb
4. sample/04_procedural_writer.ipynb
5. sample/05_builder_and_reader.ipynb
6. sample/06_advanced_v2_features.ipynb
7. sample/07_v0_3_0_features.ipynb
"""

import json
import sys
from pathlib import Path


def run_notebook(nb_path: Path) -> bool:
    print(f"\n{'='*70}")
    print(f" Running {nb_path.name}...")
    print(f"{'='*70}")

    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    exec_globals = {"__name__": "__main__", "__file__": str(nb_path)}
    code_cells = [cell for cell in nb.get("cells", []) if cell.get("cell_type") == "code"]

    for idx, cell in enumerate(code_cells, 1):
        source = "".join(cell.get("source", []))
        try:
            exec(source, exec_globals)
        except Exception as e:
            print(f"FAILED in {nb_path.name} (cell {idx}): {e}", file=sys.stderr)
            return False

    print(f"PASSED: {nb_path.name} ({len(code_cells)} code cells)")
    return True


def main():
    sample_dir = Path(__file__).parent
    samples = [
        sample_dir / "01_basic_struct.ipynb",
        sample_dir / "02_bitfields_and_alignment.ipynb",
        sample_dir / "03_offsets_and_tables.ipynb",
        sample_dir / "04_procedural_writer.ipynb",
        sample_dir / "05_builder_and_reader.ipynb",
        sample_dir / "06_advanced_v2_features.ipynb",
        sample_dir / "07_v0_3_0_features.ipynb",
    ]

    print("======================================================================")
    print(" Binary Master: Executing All Jupyter Notebook Samples")
    print("======================================================================")

    all_passed = True
    for sample in samples:
        if not run_notebook(sample):
            all_passed = False
            break

    print("\n" + "=" * 70)
    if all_passed:
        print(" ALL 7 NOTEBOOK SAMPLES COMPLETED SUCCESSFULLY!")
    else:
        print(" SOME SAMPLES FAILED!")
    print("=" * 70)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
