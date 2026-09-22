#!/bin/python3
# -*- coding: utf-8 -*-
import sys
import os
import re
from datetime import datetime
import getpass
import yaml


def main():
    try:
        para_list = sys.argv[1:]
    except Exception as e:
        print("Error parameters!!! unknown parameter")
        print(e)
        sys.exit(1)

    protocol = para_list[1]

    with open(para_list[0], 'r') as file:
        data = yaml.safe_load(file)

    yml2regfile(data, protocol)


def yml2regfile(data, protocol):
    """Reuse the maintained register generator; keep the CRG-specific interface."""
    import copy
    import runpy
    from pathlib import Path
    if protocol != "apb":
        raise ValueError("CRG register generation currently implements APB only; no placeholder bus RTL")
    data = copy.deepcopy(data)
    for register in data["registers"]:
        for field in register["fields"]:
            field["name"] = register["name"] + "_" + field["name"]
    scripts = Path(__file__).resolve().parents[3] / "yml2reg" / "scripts"
    backend = scripts / "yml2reg.py"
    if not backend.is_file():
        raise FileNotFoundError("CRG requires the sibling yml2reg skill; install both from the same kit export")
    loaded = sys.modules.get("yml_model")
    if loaded is not None and Path(loaded.__file__).resolve() != (scripts / "yml_model.py").resolve():
        raise RuntimeError("A different yml_model is already loaded; refusing mixed generator versions")
    previous = list(sys.path)
    try:
        sys.path.insert(0, str(scripts))
        return runpy.run_path(str(backend))["yml2regfile"](data, protocol)
    finally:
        sys.path[:] = previous


def parse_bit_ranges(ranges):
    parsed_ranges = set()
    for range_str in ranges:
        a, b = map(int, range_str.split(':'))
        parsed_ranges.update(range(min(a, b), max(a, b) + 1))
    return parsed_ranges


def generate_full_range(max_width):
    return set(range(max_width + 1))


def find_missing_bits(parsed_ranges, full_range):
    missing_bits = full_range - parsed_ranges
    return missing_bits


def merge_consecutive_bits(bits_set):
    if not bits_set:
        return []
    sorted_bits = sorted(bits_set)
    ranges = []
    start = sorted_bits[0]
    end = sorted_bits[0]
    for b in sorted_bits[1:]:
        if b == end + 1:
            end = b
        else:
            ranges.append((start, end))
            start = b
            end = b
    ranges.append((start, end))
    return ranges


def add_header(print_line, filename):
    today = datetime.today()
    now = datetime.now()
    user = getpass.getuser()

    date1 = today.strftime("%Y/%m/%d")
    year = today.strftime("%Y")
    time = now.strftime("%H:%M")

    print_line.append("// +FHDR----------------------------------------------------------------------------")
    print_line.append("// Copyright (c) " + year + " Silicon Peasant.")
    print_line.append("// ALL RIGHTS RESERVED Worldwide")
    print_line.append("//         ")
    print_line.append("// Author        : " + user)
    print_line.append("// Email         : " + user + "@foxmail.com")
    print_line.append("// Created On    : " + date1 + " " + time)
    print_line.append("// Last Modified : " + date1 + " " + time)
    print_line.append("// File Name     : " + filename)
    print_line.append("// Description   :")
    print_line.append("// ")
    print_line.append("// ---------------------------------------------------------------------------------")
    print_line.append("// Modification History:")
    print_line.append("// Date         By              Version                 Change Description")
    print_line.append("// ---------------------------------------------------------------------------------")
    print_line.append("// " + date1 + "   " + user + "     1.0                     Original")
    print_line.append("// -FHDR----------------------------------------------------------------------------")


if __name__ == "__main__":
    main()
