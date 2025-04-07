#!/bin/bash

while true; do
    # Use -u (unbuffered) to ensure that output is printed immediately
    python -u -m IConfucius_agent_quotes
    sleep 10800  # Sleep for 10800 seconds (3 hours)
done
