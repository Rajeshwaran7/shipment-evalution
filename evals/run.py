"""CLI Entrypoint for running evals directly with python -m evals.run."""

import argparse
from evals.runner import run_eval_suite


def main():
    parser = argparse.ArgumentParser(description="Run ExceptionOps Benchmark Eval Suite")
    parser.add_argument("--prompt-version", default="v1", help="Prompt version tag (e.g. v1, v2)")
    parser.add_argument("--model", default=None, help="LLM model name")
    parser.add_argument("--category", default=None, help="Filter by scenario category")

    args = parser.parse_args()
    run_eval_suite(
        prompt_version=args.prompt_version,
        model_name=args.model,
        category_filter=args.category,
    )


if __name__ == "__main__":
    main()

