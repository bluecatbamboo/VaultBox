#!/bin/bash
set -e

# Ensure data and logs directories exist
mkdir -p data logs

# Create the database only if it does not exist (for new containers)
if [ ! -f data/emails.db ]; then
    echo "Database not found, creating new data/emails.db..."
    python create_db.py
else
    echo "Database already exists, skipping creation."
fi

# Pass control to the main run script
exec ./run.sh start
