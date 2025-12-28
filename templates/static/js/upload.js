document.addEventListener('DOMContentLoaded', function() {
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const uploadButton = document.getElementById('upload-button');
    const uploadProgress = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const uploadStatus = document.getElementById('upload-status');
    const resultsSection = document.getElementById('results-section');
    const resultsContainer = document.getElementById('results-container');
    
    let filesToUpload = [];

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropArea.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', handleFileSelect, false);
    uploadButton.addEventListener('click', handleUpload);

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropArea.classList.add('highlight');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFileSelect(e) {
        const files = e.target.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        filesToUpload = [...filesToUpload, ...files];
        updateFileList();
        updateUploadButton();
    }

    function updateFileList() {
        fileList.innerHTML = '';
        
        filesToUpload.forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.setAttribute('data-filename', file.name);
            fileItem.innerHTML = `
                <div class="file-info">
                    <i class="file-icon far ${getFileIcon(file.name)}"></i>
                    <div>
                        <div class="file-name">${file.name}</div>
                        <div class="file-size">${formatFileSize(file.size)}</div>
                    </div>
                </div>
                <div class="file-actions">
                    <span class="file-remove" data-index="${index}">
                        <i class="fas fa-times"></i>
                    </span>
                </div>
            `;
            fileList.appendChild(fileItem);
        });

        // Add event listeners to remove buttons
        document.querySelectorAll('.file-remove').forEach(button => {
            button.addEventListener('click', (e) => {
                const index = parseInt(e.currentTarget.getAttribute('data-index'));
                filesToUpload.splice(index, 1);
                updateFileList();
                updateUploadButton();
            });
        });
    }

    function updateUploadButton() {
        uploadButton.disabled = filesToUpload.length === 0;
    }

    function getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            'pdf': 'fa-file-pdf',
            'doc': 'fa-file-word',
            'docx': 'fa-file-word',
            'xls': 'fa-file-excel',
            'xlsx': 'fa-file-excel',
            'ppt': 'fa-file-powerpoint',
            'pptx': 'fa-file-powerpoint',
            'txt': 'fa-file-alt',
            'zip': 'fa-file-archive',
            'rar': 'fa-file-archive',
            'jpg': 'fa-file-image',
            'jpeg': 'fa-file-image',
            'png': 'fa-file-image',
            'gif': 'fa-file-image'
        };
        return icons[ext] || 'fa-file';
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async function handleUpload() {
        if (filesToUpload.length === 0) return;

        const formData = new FormData();
        filesToUpload.forEach(file => {
            formData.append('files', file);
        });

        // Show progress UI
        uploadProgress.classList.remove('hidden');
        uploadButton.disabled = true;
        uploadStatus.textContent = 'Preparing to upload...';
        
        try {
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    updateProgress(percentComplete);
                    const currentFile = filesToUpload[0]?.name || 'files';
                    uploadStatus.textContent = `Uploading ${currentFile}: ${percentComplete}%`;
                }
            });
            
            // Track currently processing file
            let currentFileIndex = 0;
            const updateCurrentFile = () => {
                if (currentFileIndex < filesToUpload.length) {
                    const currentFile = filesToUpload[currentFileIndex];
                    const fileItem = document.querySelector(`.file-item[data-filename="${currentFile.name}"]`);
                    if (fileItem) {
                        // Remove processing class from all files
                        document.querySelectorAll('.file-item').forEach(item => {
                            item.classList.remove('processing');
                        });
                        // Add processing class to current file
                        fileItem.classList.add('processing');
                        
                        // Update status text
                        const statusEl = fileItem.querySelector('.file-status') || document.createElement('div');
                        statusEl.className = 'file-status text-blue-600 text-sm mt-1';
                        statusEl.textContent = 'Processing...';
                        if (!fileItem.querySelector('.file-status')) {
                            fileItem.querySelector('.file-info').appendChild(statusEl);
                        }
                    }
                }
            };
            
            // Initial update
            updateCurrentFile();

            xhr.addEventListener('load', () => {
                if (xhr.status === 200) {
                    const response = JSON.parse(xhr.responseText);
                    showResults(response);
                } else {
                    throw new Error('Upload failed');
                }
            });

            xhr.addEventListener('error', () => {
                throw new Error('Upload failed. Please try again.');
            });

            xhr.open('POST', '/api/rate/upload', true);
            xhr.send(formData);

        } catch (error) {
            console.error('Upload error:', error);
            uploadStatus.textContent = `Error: ${error.message}`;
            uploadStatus.className = 'text-red-500';
            uploadButton.disabled = false;
        }
    }

    function updateProgress(percent) {
        progressBar.style.width = `${percent}%`;
        progressPercent.textContent = `${percent}%`;
        
        if (percent === 100) {
            progressBar.classList.add('uploading');
            uploadStatus.textContent = 'Processing files...';
        } else {
            progressBar.classList.remove('uploading');
        }
    }

    function showResults(response) {
        // Hide progress bar
        uploadProgress.classList.add('hidden');
        
        // Show results section
        resultsSection.classList.remove('hidden');
        resultsContainer.innerHTML = '';
        
        if (response.success) {
            // Display successful uploads
            if (response.data && response.data.results && response.data.results.successful) {
                response.data.results.successful.forEach(file => {
                    const resultCard = document.createElement('div');
                    resultCard.className = 'result-card result-success';
                    resultCard.innerHTML = `
                        <div class="flex items-start">
                            <i class="fas fa-check-circle text-green-500 text-xl mt-1 mr-3"></i>
                            <div>
                                <h3 class="font-medium text-gray-800">${file.file_path.split('/').pop()}</h3>
                                <p class="text-sm text-gray-600">Processed successfully</p>
                                <div class="mt-2 p-2 bg-gray-50 rounded text-sm">
                                    <pre class="whitespace-pre-wrap">${JSON.stringify(file.result, null, 2)}</pre>
                                </div>
                            </div>
                        </div>
                    `;
                    resultsContainer.appendChild(resultCard);
                });
            }
            
            // Display failed uploads
            if (response.data && response.data.results && response.data.results.failed) {
                response.data.results.failed.forEach(file => {
                    const resultCard = document.createElement('div');
                    resultCard.className = 'result-card result-error';
                    resultCard.innerHTML = `
                        <div class="flex items-start">
                            <i class="fas fa-times-circle text-red-500 text-xl mt-1 mr-3"></i>
                            <div>
                                <h3 class="font-medium text-gray-800">${file.file_path || 'Unknown file'}</h3>
                                <p class="text-sm text-red-500">Error: ${file.error || 'Unknown error'}</p>
                            </div>
                        </div>
                    `;
                    resultsContainer.appendChild(resultCard);
                });
            }
            
            // Scroll to results
            resultsSection.scrollIntoView({ behavior: 'smooth' });
            
        } else {
            // Show error message
            const errorCard = document.createElement('div');
            errorCard.className = 'result-card result-error';
            errorCard.innerHTML = `
                <div class="flex items-start">
                    <i class="fas fa-exclamation-triangle text-red-500 text-xl mt-1 mr-3"></i>
                    <div>
                        <h3 class="font-medium text-gray-800">Error Processing Files</h3>
                        <p class="text-sm text-red-500">${response.error || 'An unknown error occurred'}</p>
                    </div>
                </div>
            `;
            resultsContainer.appendChild(errorCard);
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Reset the form
        filesToUpload = [];
        updateFileList();
        uploadButton.disabled = false;
    }
});
