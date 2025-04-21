#!/bin/bash

while true; do
    # Use -u (unbuffered) to ensure that output is printed immediately
    python -u -m IConfucius_agent_quotes
    sleep 600  # Sleep for 600 seconds (10 minutes)
done
