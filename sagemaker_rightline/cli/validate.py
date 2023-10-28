import argparse
import importlib.util
import logging
import os

from sagemaker_rightline.model import Configuration


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
        default=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    return args  # pragma: no cover


def load_configuration(config_file_path: str) -> Configuration:
    """Fetch the configuration object from the specified file.

    :param config_file_path: Path to the file that holds a Configuration object.
    :type config_file_path: str
    :return: Configuration object.
    :rtype: Configuration
    """
    abs_path = os.path.abspath(config_file_path)
    spec = importlib.util.spec_from_file_location("get_configuration", abs_path)
    sm_rightline_config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sm_rightline_config_module)
    return sm_rightline_config_module.get_configuration()


def main():
    """Run the configuration."""
    args = parse_args()
    if "working_dir" in args:
        os.chdir(os.path.abspath(args.working_dir))

    cm = load_configuration(args.configuration)
    df_report = cm.run(return_df=True)
    if not df_report["success"].all():
        # Non-zero exit (unsuccessful) if there are any failed validations.
        logging.error(df_report)
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
