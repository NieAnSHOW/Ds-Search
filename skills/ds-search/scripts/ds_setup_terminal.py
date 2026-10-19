"""Child process for visible terminal setup; never receives a secret argument."""
import sys

import ds_search


def main() -> int:
    status = ds_search.main(['setup', '--storage', 'keyring'])
    if not sys.stdin.isatty():
        return status
    try:
        input('按 Enter 结束初始化。')
    except (EOFError, KeyboardInterrupt):
        pass
    return status


if __name__ == '__main__':
    sys.exit(main())
