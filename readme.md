# 🔥 Incident Events Upload

A web application that allows users to bulk upload incident events to Amplitude via CSV files. The application provides a user-friendly interface with drag-and-drop functionality and preview capabilities.

## Features

- Drag-and-drop CSV file upload
- File selection via browser
- Preview of uploaded data (up to 5 rows)
- Validation of CSV format and data
- Bulk sending of events to Amplitude
- Responsive design
- Sample data templates provided

## Prerequisites

- Python 3.7+
- Flask
- Amplitude Analytics account

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd incident-events-upload
```

2. Install required dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with:

```env
AMPLITUDE_API_KEY=<your-amplitude-api-key>
```

## Running Locally

1. Start the Flask application:

```bash
python app.py
```

2. Open your browser and navigate to `http://127.0.0.1:8080` to access the application.


## CSV File Format

The CSV file must contain the following columns in this exact order:
- `user_id`: Unique identifier for the user
- `incident_name`: Name of the incident
- `short_description`: Brief description of the incident
- `datetime`: Date and time of the incident (format: MM/DD/YYYY HH:MM)

Example:

```csv
user_id,incident_name,short_description,datetime
12345,Incident 1,Description of Incident 1,01/01/2024 10:00
67890,Incident 2,Description of Incident 2,01/02/2024 11:00
```