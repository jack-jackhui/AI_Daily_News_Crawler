#!/bin/bash

# Create the main 'src' directory
mkdir -p src

# Create subdirectories inside 'src'
mkdir -p src/fetchers
mkdir -p src/processors
mkdir -p src/outputs
mkdir -p src/scheduler

# Create the '__init__.py' files in relevant directories
touch src/__init__.py
touch src/fetchers/__init__.py
touch src/processors/__init__.py
touch src/outputs/__init__.py
touch src/scheduler/__init__.py

# Create the other files in their respective directories
touch src/config.py
touch src/fetchers/crawler.py
touch src/fetchers/orchestrator.py
touch src/processors/summarizer.py
touch src/processors/formatter.py
touch src/outputs/telegram_sender.py
touch src/outputs/local_storage.py
touch src/scheduler/schedule_tasks.py
touch src/main.py

# Create the requirements.txt, README.md and.env files in the root directory
touch requirements.txt
touch README.md
touch .env

echo "Project folder and file structure created successfully."