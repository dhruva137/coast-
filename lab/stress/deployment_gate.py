#!/usr/bin/env python3
"""Convenience entry point for the SIH26168 deployment readiness gate."""

from product_gate import main


if __name__ == "__main__":
    raise SystemExit(main(["--level", "deployment"]))
