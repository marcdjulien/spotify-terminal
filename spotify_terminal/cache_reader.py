#!/usr/bin/env python3
import argparse
import IPython
import pdb
import pickle
import sys

parser = argparse.ArgumentParser(description="Debugging tool to read cached items.")
parser.add_argument("filename", help="The cached file")
parser.add_argument("-i",
                    action="store_true",
                    default=False,
                    dest="interactive",
                    help="interactive mode")
args = parser.parse_args()

with open(args.filename, "rb") as obj_file:
    obj = pickle.load(obj_file)
    print("="*50)
    print(type(obj))
    if hasattr(obj, "info"):
        print(getattr(obj, "info"))
    print(dir(obj))

if args.interactive:
    try:
        IPython.embed()
    except Exception:
        pdb.set_trace()
