#!/bin/bash

# Start the MOV converter service in the background
python mov_converter_service.py &

# Start the web application
uvicorn main:app --host 0.0.0.0 --port 8000
