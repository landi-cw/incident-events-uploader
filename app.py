import os
import csv
import logging
from flask import Flask, request, send_from_directory, render_template, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from amplitude import Amplitude, BaseEvent
import tempfile

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB
app.config['UPLOAD_EXTENSIONS'] = ['.csv']

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize Amplitude client
AMPLITUDE_API_KEY = os.getenv('AMPLITUDE_API_KEY')
if not AMPLITUDE_API_KEY:
    logging.error("Amplitude API key not set.")
    exit(1)
amplitude_client = Amplitude(api_key=AMPLITUDE_API_KEY)

# Global variable to store uploaded data
uploaded_data = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/upload', methods=['POST'])
def upload_file():
    global uploaded_data
    if 'file' not in request.files:
        logging.error("No file part in the request.")
        return "No file part.", 400

    file = request.files['file']
    if file.filename == '':
        logging.error("No selected file.")
        return "No selected file.", 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.csv'):
        logging.error(f"Invalid file type: {filename}")
        return "Please upload a valid CSV file.", 400

    try:
        # Save the file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
            file.save(tmp.name)
            temp_file_path = tmp.name

        # Process the CSV file
        data = process_csv(temp_file_path)
        uploaded_data = data

        # Generate HTML response
        html_response = generate_html_response(filename, data)

        return html_response, 200

    except Exception as e:
        logging.error(f"Error processing file: {e}")
        return "Failed to process the uploaded file. Please check your CSV file and follow the required column order from the sample data.", 500
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def process_csv(filename):
    REQUIRED_COLUMNS = ['user_id', 'incident_name', 'short_description', 'datetime']
    
    with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        records = list(reader)
        
        if not records or len(records) < 2:
            raise ValueError("CSV file is empty or contains only headers")
            
        headers = records[0]
        
        # Validate column order
        if headers != REQUIRED_COLUMNS:
            raise ValueError(f"CSV columns must be in order: {', '.join(REQUIRED_COLUMNS)}")
        
        # Validate data rows
        for row_num, row in enumerate(records[1:], start=2):
            if len(row) != len(headers):
                raise ValueError(f"Row {row_num} has incorrect number of columns")
                
            # Check for empty values in required fields
            if not row[0].strip():  # user_id
                raise ValueError(f"Row {row_num}: user_id cannot be empty")
            if not row[1].strip():  # incident_name
                raise ValueError(f"Row {row_num}: incident_name cannot be empty")
            if not row[3].strip():  # datetime
                raise ValueError(f"Row {row_num}: datetime cannot be empty")
                
    return records

def generate_html_response(filename, data):
    if not data:
        return "<p>No data found in the CSV file.</p>"

    headers = data[0]
    rows = data[1:]
    total_rows = len(rows)

    # Limit preview to first 5 rows
    preview_rows = rows[:5]

    # Generate HTML table
    table_html = "<table>"
    table_html += "<tr>"
    for header in headers:
        table_html += f"<th>{html_escape(header)}</th>"
    table_html += "</tr>"

    for row in preview_rows:
        table_html += "<tr>"
        for cell in row:
            table_html += f"<td>{html_escape(cell)}</td>"
        table_html += "</tr>"
    table_html += "</table>"

    html = f"""
    <div id="preview-container">
        <h2 class="preview-header">Preview Results</h2>
        <h3 class="preview-detail">Preview is up to 5 rows</h3>
        <p class="preview-filename"><strong class="preview-bold">Filename:</strong> {html_escape(filename)}</p>
        <p class="preview-total-rows"><strong class="preview-bold">Total Rows:</strong> {total_rows}</p>
        {table_html}
    </div>
    """
    return html

def html_escape(text):
    """Escape HTML special characters in text."""
    import html
    return html.escape(text)

@app.route('/cancel', methods=['POST'])
def cancel_upload():
    global uploaded_data
    uploaded_data = []
    return "Upload cancelled.", 200

@app.route('/send-events', methods=['POST'])
def send_events():
    global uploaded_data
    if not uploaded_data or len(uploaded_data) < 2:
        return "No data to send.", 400

    headers = uploaded_data[0]
    user_id_idx = headers.index('user_id')
    incident_name_idx = headers.index('incident_name')
    description_idx = headers.index('short_description')
    datetime_idx = headers.index('datetime')

    for record in uploaded_data[1:]:
        try:
            user_id = record[user_id_idx]
            incident_name = record[incident_name_idx]
            description = record[description_idx]
            timestamp_str = record[datetime_idx]

            # Ensure timestamp has time component
            if len(timestamp_str) == 10:
                timestamp_str += " 00:00"

            # Parse timestamp directly as UTC
            from datetime import datetime
            import pytz
            try:
                dt = datetime.strptime(timestamp_str, "%m/%d/%Y %H:%M")
                dt = pytz.utc.localize(dt)  # Mark the time as UTC
                unix_timestamp = int(dt.timestamp() * 1000)
            except ValueError as ve:
                logging.error(f"Error parsing timestamp for user_id {user_id}: {ve}")
                continue

            # Validate user_id length
            if len(user_id) < 5:
                logging.warning(f"Skipping event for user_id {user_id}: ID length is less than 5 characters")
                continue

            # Create and send event to Amplitude
            event = BaseEvent(
                user_id=user_id,
                event_type="Incident",
                event_properties={
                    "name": incident_name,
                    "description": description
                },
                time=unix_timestamp
            )
            amplitude_client.track(event)

        except Exception as e:
            logging.error(f"Error sending event for user_id {user_id}: {e}")
            continue

    amplitude_client.flush()
    return "Events sent successfully.", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
