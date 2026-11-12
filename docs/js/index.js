document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('file');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressLabel = document.getElementById('progress-label');
    const dropZone = document.getElementById('drop-zone');
    const form = document.querySelector('form');
    const errorMessage = document.getElementById('error-message');
    let fileSelected = false;
    let uploading = false;

    // Function to show error message
    function showError(message) {
        const errorText = document.getElementById('error-text');
        errorText.textContent = message;
        errorMessage.style.display = 'flex';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            hideError();
        }, 5000);
    }

    // Function to hide error message
    function hideError() {
        errorMessage.style.display = 'none';
    }

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop zone when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);

    // File input change handler
    fileInput.addEventListener('change', handleFileSelect);
    
    // Remove file handler
    const removeFileBtn = document.getElementById('remove-file-btn');
    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', function(e) {
            e.preventDefault();
            fileInput.value = '';
            progressContainer.style.display = 'none';
            fileSelected = false;
        });
    }

    // Form submission handler
    form.addEventListener('submit', function(e) {
        if (!fileSelected) {
            e.preventDefault();
            showError('Please select a file.');
            return false;
        }
        
        // Double-check file type before submission
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            const allowedExtensions = ['pdf', 'docx'];
            const fileName = file.name.toLowerCase();
            const fileExtension = fileName.split('.').pop();
            
            if (!allowedExtensions.includes(fileExtension)) {
                e.preventDefault();
                showError('INVALID FILE TYPE: Only PDF and DOCX files are allowed.');
                fileInput.value = '';
                progressContainer.style.display = 'none';
                fileSelected = false;
                return false;
            }
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
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length) {
            fileInput.files = files;
            const event = new Event('change');
            fileInput.dispatchEvent(event);
        }
    }

    function handleFileSelect(e) {
        if (fileInput.files.length > 0) {
            const file = fileInput.files[0];
            
            // Validate file type
            const allowedExtensions = ['pdf', 'docx'];
            const fileName = file.name.toLowerCase();
            const fileExtension = fileName.split('.').pop();
            
            if (!allowedExtensions.includes(fileExtension)) {
                showError('INVALID FILE TYPE: Only PDF and DOCX files are allowed.');
                fileInput.value = ''; // Clear the file input
                progressContainer.style.display = 'none';
                fileSelected = false;
                return; // Stop processing
            }
            // Validate file size (100 MB limit)
            const maxFileSize = 50 * 1024 * 1024; // 50 MB in bytes
            if (file.size > maxFileSize) {
                showError('FILE TOO LARGE: Maximum file size is 50 MB. Your file is ' + (file.size/1024/1024).toFixed(1) + ' MB.');
                fileInput.value = ''; // Clear the file input
                progressContainer.style.display = 'none';
                fileSelected = false;
                return; // Stop processing
            }
            // Hide error message if file is valid
            hideError();
            
            // Show file info
            document.getElementById('file-name').textContent = file.name;
            document.getElementById('file-size').textContent = (file.size/1024/1024).toFixed(1) + ' MB';
            
            // Thumbnail if image
            const thumbImg = document.getElementById('file-thumb-img');
            const thumbIcon = document.getElementById('file-thumb-icon');
            if (file.type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    thumbImg.src = e.target.result;
                    thumbImg.style.display = 'block';
                    thumbIcon.style.display = 'none';
                };
                reader.readAsDataURL(file);
            } else {
                thumbImg.style.display = 'none';
                thumbIcon.style.display = 'block';
            }
            
            progressContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressLabel.textContent = '0%';
            fileSelected = true;
            
            // Animate progress bar instantly on file select
            let percent = 0;
            function animateBar() {
                if (percent < 100) {
                    percent += 2 + Math.random()*2;
                    if (percent > 100) percent = 100;
                    progressBar.style.width = percent + '%';
                    progressLabel.textContent = Math.floor(percent) + '%';
                    setTimeout(animateBar, 15);
                } else {
                    progressBar.style.width = '100%';
                    progressLabel.textContent = '100%';
                }
            }
            animateBar();
        } else {
            progressContainer.style.display = 'none';
            fileSelected = false;
        }
    }
});
