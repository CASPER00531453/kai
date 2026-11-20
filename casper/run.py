"""Casper Patrick Jane'i başlat:  python run.py   (geliştirici araçlarıyla: python run.py --debug)"""

import sys

from casper.app import CasperApp

if __name__ == "__main__":
    CasperApp().run(debug="--debug" in sys.argv)
