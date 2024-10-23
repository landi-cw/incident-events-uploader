// DOM Element Selection
const dropZone = document.getElementById('drop-zone');
const processingIndicator = document.getElementById('processing');
const fileInput = document.getElementById('file-input');

// Drag and Drop Event Handlers
// Handles when file is being dragged over the drop zone
dropZone.addEventListener('dragover', function(e) {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

// Handles when file is being dragged into the drop zone
dropZone.addEventListener('dragenter', function(e) {
    e.preventDefault(); 
    dropZone.classList.add('dragover');
});

// Handles when file is being dragged out of the drop zone
dropZone.addEventListener('dragleave', function(e) {
    e.preventDefault();
    dropZone.classList.remove('dragover');
});

// File Input Handler
// Handles file selection from explorer
fileInput.addEventListener('change', function(e) {
    if (e.target.files.length > 0) {
        handleFileUpload(e.target.files[0]);
    }
});

// File Drop Handler
// Processes the dropped file and sends it to the server
dropZone.addEventListener('drop', function(e) {
    e.preventDefault();
    dropZone.classList.remove('dragover');

    if (e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files[0]);
    }
});

// Common file upload handler
function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);

    // Show processing status
    processingIndicator.innerHTML = "Processing...";

    // Send file to server and handle response
    fetch('/upload', {
        method: 'POST',
        body: formData,
    })
    .then(response => response.text())
    .then(html => {
        // Update UI with preview and show action buttons
        document.getElementById('result').innerHTML = html;
        processingIndicator.innerHTML = "";
        document.getElementById('cancel-button').style.display = 'block';
        document.getElementById('send-events-button').style.display = 'block';
    })
    .catch(err => {
        // Handle errors
        processingIndicator.innerHTML = "An error occurred during upload.";
        console.error(err);
    });
}

// Cancel Button Handler
// Cancels the current upload operation
document.getElementById('cancel-button').addEventListener('click', function() {
    fetch('/cancel', { method: 'POST' })
        .then(() => {
            document.getElementById('result').innerHTML = "Your results preview will show here";
            document.getElementById('cancel-button').style.display = 'none';
            document.getElementById('send-events-button').style.display = 'none';
        })
        .catch(err => console.error(err));
});

// Send Events Button Handler
// Triggers the actual event sending process
document.getElementById('send-events-button').addEventListener('click', function() {
    if (confirm('Are you sure you want to send these events to Amplitude?')) {
        fetch('/send-events', { method: 'POST' })
            .then(response => response.text())
            .then(message => {
                alert(message);
                window.location.reload();
            })
            .catch(err => console.error(err));
    }
});
