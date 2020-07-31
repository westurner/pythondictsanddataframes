#!/usr/bin/env python


def main():
    import sys
    import logging
    logging.basicConfig()
    log = logging.getLogger(__file__)
    log.setLevel(logging.DEBUG)

    filename = sys.argv[1]
    log.info(('filename', filename))

    with open(filename, 'r') as f:
        data = f.read() \
            .replace('```\n\n\n', '```\n\n') \
            .replace('\n\n\n', '\n\n') \
            .replace('\n\n\n```', '\n\n```')

        lines = data.splitlines()
        newdata = '\n'.join(l for l in lines if not l.startswith('<!--'))

        log.debug(('newdata', newdata))

    with open(filename, 'w') as f:
        f.write(newdata)

if __name__ == "__main__":
    main()
