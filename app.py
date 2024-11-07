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
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB
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

    successful_events = 0
    failed_events = 0
    total_events = len(uploaded_data[1:])

    logging.info(f"Starting to process {total_events} events...")

    for record in uploaded_data[1:]:
        try:
            user_id = record[user_id_idx]
            incident_name = record[incident_name_idx]
            description = record[description_idx]
            timestamp_str = record[datetime_idx]

            # Parse timestamp with multiple format support
            from datetime import datetime
            import pytz

            # Try different timestamp formats
            timestamp_formats = [
                "%m/%d/%Y %H:%M",           # Original format: "03/15/2024 13:30"
                "%Y-%m-%d %H:%M:%S.%f %Z",  # New format: "2024-10-03 13:59:39.598 UTC"
                "%Y-%m-%d %H:%M:%S %Z"      # Alternative without milliseconds
            ]

            dt = None
            for fmt in timestamp_formats:
                try:
                    if 'UTC' in timestamp_str:
                        dt = datetime.strptime(timestamp_str, fmt)
                        if fmt.endswith('%Z'):
                            dt = dt.replace(tzinfo=pytz.UTC)
                    else:
                        dt = datetime.strptime(timestamp_str, fmt)
                        dt = pytz.utc.localize(dt)
                    break
                except ValueError:
                    continue

            if dt is None:
                raise ValueError(f"Could not parse timestamp: {timestamp_str}")

            unix_timestamp = int(dt.timestamp() * 1000)

            # Create and send event to Amplitude
            event = BaseEvent(
                user_id=user_id,
                event_type="Incident",
                event_properties={
                    "name": incident_name,
                    "description": description,
                    "original_timestamp": timestamp_str
                },
                time=unix_timestamp
            )
            amplitude_client.track(event)
            successful_events += 1
            logging.info(
                f"Event {successful_events}/{total_events} sent successfully:\n"
                f"  User ID: {user_id}\n"
                f"  Incident: {incident_name}\n"
                f"  Time: {timestamp_str}\n"
                f"  Description: {description[:100]}{'...' if len(description) > 100 else ''}"
            )

        except Exception as e:
            failed_events += 1
            logging.error(
                f"Failed to send event {successful_events + failed_events}/{total_events}:\n"
                f"  User ID: {user_id}\n"
                f"  Error: {str(e)}"
            )
            continue

    amplitude_client.flush()
    
    result_message = (
        f"Processing complete. "
        f"Successfully sent {successful_events} events, "
        f"Failed to send {failed_events} events."
    )
    logging.info(result_message)
    
    if failed_events > 0 and successful_events > 0:
        return f"Partial success. Sent {successful_events} events, {failed_events} events failed to send.", 207  # Multi-Status
    elif failed_events > 0:
        return f"Failed to send {failed_events} events.", 207  # Multi-Status
    return f"Successfully sent {successful_events} events.", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
