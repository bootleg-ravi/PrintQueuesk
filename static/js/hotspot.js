// Import Firebase SDK modules via CDN
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getStorage, ref as storageRef, uploadBytesResumable, getDownloadURL } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-storage.js";
import { getDatabase, ref as dbRef, push, set } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-database.js";

// TODO: Replace these with your actual Firebase project configuration details
const firebaseConfig = {
  apiKey: "AIzaSyCofkkAfT8-NY8LVUNuuvPQzlvbnJ4p1nI",
  authDomain: "printqueuesk-f2c93.firebaseapp.com",
  databaseURL: "https://printqueuesk-f2c93-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "printqueuesk-f2c93",
  storageBucket: "printqueuesk-f2c93.firebasestorage.app",
  messagingSenderId: "883624271026",
  appId: "1:883624271026:web:2123e2f5a3b3f5a9113dab"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const storage = getStorage(app);
const database = getDatabase(app);

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

        try {
            // Create a unique file name to avoid collisions in Storage
            const uniqueFileName = `${Date.now()}_${fileToUpload.name}`;
            const fileStorageRef = storageRef(storage, `print_files/${uniqueFileName}`);
            
            // Start resumable upload to Firebase Storage
            const uploadTask = uploadBytesResumable(fileStorageRef, fileToUpload);

            uploadTask.on('state_changed', 
                (snapshot) => {
                    // Track upload progress
                    const progress = (snapshot.bytesTransferred / snapshot.totalBytes) * 100;
                    progressBar.style.width = progress + '%';
                    progressLabel.textContent = Math.round(progress) + '%';
                }, 
                (error) => {
                    console.error('Firebase Storage error:', error);
                    throw new Error(error.message);
                }, 
                async () => {
                    // Upload completed successfully, get the public download URL
                    const downloadURL = await getDownloadURL(uploadTask.snapshot.ref);

                    // Push job record to Firebase Realtime Database so the Python desktop app picks it up
                    const newJobRef = push(dbRef(database, 'jobs/print_jobs'));
                    await set(newJobRef, {
                        file_name: fileToUpload.name,
                        file_path: uniqueFileName,
                        download_url: downloadURL,
                        status: 'pending',
                        created_at: Date.now()
                    });

                    // Redirect to success confirmation page
                    window.location.href = `hotspot_uploaded.html?filename=${encodeURIComponent(fileToUpload.name)}`;
                }
            );

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