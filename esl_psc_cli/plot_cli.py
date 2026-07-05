from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime, timezone

from esl_psc_cli import esl_psc_functions as ecf


def _write_diagnostic_file(path: str, *, args: argparse.Namespace, exc: BaseException) -> None:
    diagnostic_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(diagnostic_path), exist_ok=True)
    with open(diagnostic_path, "w", encoding="utf-8") as handle:
        handle.write("ESL-PSC plot generation diagnostic\n")
        handle.write(f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n")
        handle.write(f"Mode: {args.mode}\n")
        handle.write(f"Predictions CSV: {os.path.abspath(args.pred_csv)}\n")
        handle.write(f"Title/output base: {args.title}\n")
        handle.write(f"Minimum genes: {args.min_genes}\n")
        if args.pheno_name1 or args.pheno_name2:
            handle.write(f"Phenotype name 1: {args.pheno_name1}\n")
            handle.write(f"Phenotype name 2: {args.pheno_name2}\n")
        handle.write("\nTraceback:\n")
        handle.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate ESL-PSC prediction plots from a species predictions CSV."
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["kde", "violin", "continuous"],
        help="Plot mode: kde, violin, or continuous",
    )
    parser.add_argument(
        "--pred_csv",
        required=True,
        help="Path to <output_base>_species_predictions.csv",
    )
    parser.add_argument(
        "--title",
        required=True,
        help="Plot title/output base name",
    )
    parser.add_argument(
        "--min_genes",
        type=int,
        default=0,
        help="Minimum genes threshold (default: 0)",
    )
    parser.add_argument(
        "--pheno_name1",
        default=None,
        help="Positive phenotype display name (binary plots only)",
    )
    parser.add_argument(
        "--pheno_name2",
        default=None,
        help="Negative phenotype display name (binary plots only)",
    )
    parser.add_argument(
        "--diagnostic_file",
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    pred_csv = os.path.abspath(args.pred_csv)
    if not os.path.isfile(pred_csv):
        print(f"Error: predictions CSV not found: {pred_csv}", file=sys.stderr)
        return 2

    try:
        if args.mode == "continuous":
            ecf.continuous_pred_plot(
                pred_csv,
                args.title,
                min_genes=int(args.min_genes),
            )
        else:
            pheno_names = None
            if args.pheno_name1 and args.pheno_name2:
                pheno_names = (str(args.pheno_name1), str(args.pheno_name2))
            ecf.rmse_range_pred_plots(
                pred_csv,
                args.title,
                pheno_names=pheno_names,
                min_genes=int(args.min_genes),
                plot_type=str(args.mode),
            )
    except Exception as exc:
        if args.diagnostic_file:
            try:
                _write_diagnostic_file(args.diagnostic_file, args=args, exc=exc)
            except Exception as diagnostic_exc:
                print(
                    f"Error: plot generation failed: {exc}; also failed to write diagnostic file: {diagnostic_exc}",
                    file=sys.stderr,
                )
                return 1
            print(
                f"Error: plot generation failed: {exc}. Diagnostic written to {os.path.abspath(args.diagnostic_file)}",
                file=sys.stderr,
            )
            return 1
        print(f"Error: plot generation failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
