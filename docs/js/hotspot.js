document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('file');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressLabel = document.getElementById('progress-label');
    const dropZone = document.getElementById('drop-zone');
    const form = document.getElementById('uploadForm');
    const uploadBtn = form.querySelector('button[type="submit"]');
    const errorMessage = document.getElementById('error-message');
    let fileToUpload = null;

    function showError(message) {
        const errorText = document.getElementById('error-text');
        errorText.textContent = message;
        errorMessage.style.display = 'flex';
        setTimeout(() => hideError(), 5000);
    }

    function hideError() {
        errorMessage.style.display = 'none';
    }

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => dropZone.addEventListener(eventName, highlight, false));
    ['dragleave', 'drop'].forEach(eventName => dropZone.addEventListener(eventName, unhighlight, false));

    dropZone.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', handleFileSelect);

    document.getElementById('remove-file-btn').addEventListener('click', function(e) {
        e.preventDefault();
        fileInput.value = '';
        progressContainer.style.display = 'none';
        fileToUpload = null;
        uploadBtn.disabled = true;
    });

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        if (!fileToUpload) {
            showError('Please select a file.');
            return;
        }

        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Uploading...';

        const formData = new FormData();
        formData.append('file', fileToUpload);

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                let errorMsg = `Server error: ${response.status} ${response.statusText}`;
                try {
                    const errorBody = await response.text();
                    errorMsg += ` - ${errorBody}`;
                } catch (e) {
                    // Ignore if we can't read the error body
                }
                throw new Error(errorMsg);
            }

            const result = await response.json();

            if (result.status === 'success') {
                // Redirect on success
                window.location.href = `/success?filename=${encodeURIComponent(result.filename)}`;
            } else {
                throw new Error(result.message || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            showError(`Upload failed: ${error.message}`);
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Submit';
        }
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropZone.style.borderColor = '#007bff';
        dropZone.style.background = '#f0f7ff';
    }

    function unhighlight() {
        dropZone.style.borderColor = '#b2b2b2';
        dropZone.style.background = '#fafbfc';
    }

    function handleDrop(e) {
        const files = e.dataTransfer.files;
        if (files.length) {
            fileInput.files = files;
            const event = new Event('change', { bubbles: true });
            fileInput.dispatchEvent(event);
        }
    }

    function handleFileSelect() {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const allowedExtensions = ['pdf', 'docx'];
            const fileExtension = file.name.split('.').pop().toLowerCase();

            if (!allowedExtensions.includes(fileExtension)) {
                showError('INVALID FILE TYPE: Only PDF and DOCX files are allowed.');
                resetFileInput();
                return;
            }

            const maxFileSize = 50 * 1024 * 1024; // 50 MB
            if (file.size > maxFileSize) {
                showError(`FILE TOO LARGE: Maximum file size is 50 MB.`);
                resetFileInput();
                return;
            }

            hideError();
            fileToUpload = file;
            updateProgressUI(file);
            uploadBtn.disabled = false;
        } else {
            resetFileInput();
        }
    }

    function resetFileInput() {
        fileInput.value = '';
        progressContainer.style.display = 'none';
        fileToUpload = null;
        uploadBtn.disabled = true;
    }

    function updateProgressUI(file) {
        document.getElementById('file-name').textContent = file.name;
        document.getElementById('file-size').textContent = (file.size / 1024 / 1024).toFixed(1) + ' MB';
        progressContainer.style.display = 'block';
        progressBar.style.width = '100%'; // Show as ready
        progressLabel.textContent = '100%';
    }
});
