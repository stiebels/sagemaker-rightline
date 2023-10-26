import argparse
import importlib.util
import logging
import os


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    :return: argparse.Namespace
    :rtype: argparse.Namespace
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configuration",
        type=str,
        required=True,
        help="Path to the file that holds a Configuration object.",
    )
    parser.add_argument(
        "--working-dir",
        type=str,
        required=False,
        help="Execute from specified working directory.",
    )
    args = parser.parse_args()
    return args


def main():
    args = parse_args()

    try:
        os.chdir(os.path.abspath(args.working_dir))
    except AttributeError:
        pass

    abs_path = os.path.abspath(args.configuration)
    spec = importlib.util.spec_from_file_location("get_configuration", abs_path)
    sm_rightline_config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sm_rightline_config_module)
    cm = sm_rightline_config_module.get_configuration()

    df_report = cm.run(return_df=True)
    if not df_report["success"].all():
        logging.error(df_report)
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
