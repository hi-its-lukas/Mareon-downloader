# Mareon Invoice Bot

## Overview
A production-ready web application that automates invoice downloads from the Mareon portal and uploads them to Buchhaltungsbutler. Built with Flask and Selenium, designed to run on Replit with Docker deployment support.

## Project Structure
```
├── main.py              # Flask web application
├── database.py          # SQLite database operations
├── scraper.py           # Selenium-based Mareon scraper
├── butler_api.py        # Buchhaltungsbutler API integration
├── templates/
│   └── index.html       # Bootstrap 5 dashboard UI
├── data/                # SQLite database storage
├── downloads/           # Temporary invoice downloads
├── Dockerfile           # Docker container configuration
├── docker-compose.yml   # Docker Compose setup
└── requirements.txt     # Python dependencies
```

## Features
- Web-based dashboard for managing accounts
- Multi-account support with mandant switching
- Automatic invoice detection and download
- Upload to Buchhaltungsbutler via API
- Duplicate prevention via history tracking
- Real-time activity logging
- Background task processing

## Database Schema
- **accounts**: Stores Mareon credentials and Butler API keys
- **history**: Tracks processed invoice numbers (prevents duplicates)
- **logs**: Activity and error logging

## Running the Application
The application runs on port 5000. Start it via the workflow or:
```bash
python main.py
```

## Docker Deployment
```bash
docker-compose up -d
```

## Configuration
All credentials are managed via the Web UI and stored in SQLite database at `data/app.db`. No .env files are used.

## Recent Changes
- Initial creation: Complete application with all components
