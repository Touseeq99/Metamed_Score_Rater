document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const uploadButton = document.getElementById('upload-button');
    const resetButton = document.getElementById('reset-button');
    const clearAllButton = document.getElementById('clear-all');
    const uploadProgress = document.getElementById('upload-progress');
    const progressBar = document.getElementById('progress-bar');
    const progressPercent = document.getElementById('progress-percent');
    const uploadStatus = document.getElementById('upload-status');
    const currentFileSpan = document.getElementById('current-file');
    const resultsSection = document.getElementById('results-section');
    const resultsContainer = document.getElementById('results-container');
    const resultsSummary = document.getElementById('results-summary');
    const resultsCount = document.getElementById('results-count');
    const fileCount = document.getElementById('file-count');
    const emptyState = document.getElementById('empty-state');
    const downloadResults = document.getElementById('download-results');
    const newUploadButton = document.getElementById('new-upload');
    
    let filesToUpload = [];
    let uploadStartTime = null;
    let processingComplete = false;

    // Event Listeners
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    dropArea.addEventListener('drop', handleDrop, false);
    fileInput.addEventListener('change', handleFileSelect, false);
    uploadButton.addEventListener('click', handleUpload);
    resetButton.addEventListener('click', resetForm);
    clearAllButton.addEventListener('click', clearAllFiles);
    downloadResults.addEventListener('click', downloadResultsFile);
    newUploadButton.addEventListener('click', startNewUpload);
    
    // Keyboard support for drop area
    dropArea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropArea.classList.add('highlight');
        dropArea.classList.add('drag-over');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
        dropArea.classList.remove('drag-over');
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
        const newFiles = Array.from(files).filter(file => {
            // Check for duplicates
            return !filesToUpload.some(existingFile => 
                existingFile.name === file.name && existingFile.size === file.size
            );
        });
        
        if (newFiles.length === 0) {
            showNotification('All selected files are already in the list', 'warning');
            return;
        }
        
        filesToUpload = [...filesToUpload, ...newFiles];
        updateFileList();
        updateUploadButton();
        
        // Show success notification
        showNotification(`${newFiles.length} file(s) added successfully`, 'success');
    }

    function updateFileList() {
        if (filesToUpload.length === 0) {
            fileList.innerHTML = '';
            fileList.appendChild(emptyState.cloneNode(true));
            clearAllButton.classList.add('hidden');
        } else {
            fileList.innerHTML = '';
            clearAllButton.classList.remove('hidden');
            
            filesToUpload.forEach((file, index) => {
                const fileItem = document.createElement('div');
                fileItem.className = 'file-item';
                fileItem.setAttribute('data-filename', file.name);
                fileItem.setAttribute('data-index', index);
                fileItem.innerHTML = `
                    <div class="file-info">
                        <div class="file-icon">
                            <i class="fas ${getFileIcon(file.name)}"></i>
                        </div>
                        <div>
                            <div class="file-name" title="${file.name}">${file.name}</div>
                            <div class="file-size">${formatFileSize(file.size)}</div>
                            <div class="file-status" id="status-${index}"></div>
                        </div>
                    </div>
                    <div class="file-actions">
                        <span class="file-remove" data-index="${index}" title="Remove file">
                            <i class="fas fa-times"></i>
                        </span>
                    </div>
                `;
                fileList.appendChild(fileItem);
            });

            // Add event listeners to remove buttons
            document.querySelectorAll('.file-remove').forEach(button => {
                button.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const index = parseInt(e.currentTarget.getAttribute('data-index'));
                    removeFile(index);
                });
            });
        }
        
        // Update file count
        fileCount.textContent = filesToUpload.length;
    }

    function updateUploadButton() {
        const hasFiles = filesToUpload.length > 0;
        uploadButton.disabled = !hasFiles || processingComplete;
        resetButton.classList.toggle('hidden', !hasFiles);
    }
    
    function removeFile(index) {
        const file = filesToUpload[index];
        filesToUpload.splice(index, 1);
        updateFileList();
        updateUploadButton();
        showNotification(`Removed ${file.name}`, 'info');
    }
    
    function clearAllFiles() {
        if (filesToUpload.length === 0) return;
        
        if (confirm(`Are you sure you want to remove all ${filesToUpload.length} file(s)?`)) {
            filesToUpload = [];
            updateFileList();
            updateUploadButton();
            showNotification('All files removed', 'info');
        }
    }
    
    function resetForm() {
        filesToUpload = [];
        processingComplete = false;
        updateFileList();
        updateUploadButton();
        uploadProgress.classList.add('hidden');
        resultsSection.classList.add('hidden');
        fileInput.value = '';
        showNotification('Form reset successfully', 'info');
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
        resetButton.disabled = true;
        uploadStatus.textContent = 'Preparing to upload...';
        currentFileSpan.textContent = 'Initializing...';
        uploadStartTime = Date.now();
        
        try {
            const xhr = new XMLHttpRequest();
            
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    updateProgress(percentComplete);
                    
                    // Update current file being processed
                    const currentIndex = Math.floor((e.loaded / e.total) * filesToUpload.length);
                    const currentFile = filesToUpload[Math.min(currentIndex, filesToUpload.length - 1)];
                    if (currentFile) {
                        currentFileSpan.textContent = currentFile.name;
                        updateFileStatus(currentFile.name, 'processing', 'Uploading...');
                    }
                    
                    uploadStatus.textContent = `Uploading files: ${percentComplete}%`;
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
                        updateFileStatus(currentFile.name, 'processing', 'Processing...');
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
                    throw new Error(`Server returned status ${xhr.status}`);
                }
            });

            xhr.addEventListener('error', () => {
                throw new Error('Network error occurred. Please check your connection and try again.');
            });

            xhr.addEventListener('timeout', () => {
                throw new Error('Request timed out. Please try again.');
            });

            xhr.timeout = 300000; // 5 minutes timeout
            xhr.open('POST', '/api/rate/upload', true);
            xhr.send(formData);

        } catch (error) {
            console.error('Upload error:', error);
            uploadStatus.textContent = `Error: ${error.message}`;
            uploadStatus.className = 'text-red-600 font-medium';
            uploadButton.disabled = false;
            resetButton.disabled = false;
            showNotification(`Upload failed: ${error.message}`, 'error');
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
    
    function updateFileStatus(filename, status, message) {
        const fileItem = document.querySelector(`.file-item[data-filename="${filename}"]`);
        if (fileItem) {
            const statusEl = fileItem.querySelector('.file-status');
            if (statusEl) {
                statusEl.className = `file-status ${status}`;
                statusEl.textContent = message;
            }
            
            // Update file item class based on status
            fileItem.classList.remove('processing', 'success', 'error');
            if (status !== '') {
                fileItem.classList.add(status);
            }
        }
    }
    
    function showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 px-6 py-3 rounded-lg shadow-lg z-50 flex items-center space-x-2 fade-in`;
        
        // Set styles based on type
        const styles = {
            success: 'bg-green-500 text-white',
            error: 'bg-red-500 text-white',
            warning: 'bg-yellow-500 text-white',
            info: 'bg-blue-500 text-white'
        };
        
        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        
        notification.className += ` ${styles[type]}`;
        notification.innerHTML = `
            <i class="fas ${icons[type]}"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }

    function showResults(response) {
        // Hide progress bar
        uploadProgress.classList.add('hidden');
        
        // Show results section
        resultsSection.classList.remove('hidden');
        resultsSection.classList.add('fade-in');
        resultsContainer.innerHTML = '';
        resultsSummary.innerHTML = '';
        
        if (response.success) {
            const successful = response.data?.results?.successful || [];
            const failed = response.data?.results?.failed || [];
            const total = successful.length + failed.length;
            
            // Update results count
            resultsCount.textContent = `${total} file(s)`;
            
            // Create summary cards
            createSummaryCards(successful.length, failed.length);
            
            // Display successful uploads
            successful.forEach((file, index) => {
                setTimeout(() => {
                    updateFileStatus(file.file_path.split('/').pop(), 'success', 'Completed successfully');
                    const resultCard = createResultCard('success', file);
                    resultsContainer.appendChild(resultCard);
                }, index * 100);
            });
            
            // Display failed uploads
            failed.forEach((file, index) => {
                setTimeout(() => {
                    updateFileStatus(file.file_path || 'Unknown file', 'error', 'Processing failed');
                    const resultCard = createResultCard('error', file);
                    resultsContainer.appendChild(resultCard);
                }, (successful.length + index) * 100);
            });
            
            // Show completion notification
            const successRate = total > 0 ? Math.round((successful.length / total) * 100) : 0;
            showNotification(
                `Processing complete: ${successful.length}/${total} files successful (${successRate}%)`,
                successful.length === total ? 'success' : 'warning'
            );
            
        } else {
            // Show error message
            resultsCount.textContent = 'Error';
            const errorCard = createResultCard('error', { 
                file_path: 'System Error', 
                error: response.error || 'An unknown error occurred' 
            });
            resultsContainer.appendChild(errorCard);
            showNotification(`Processing failed: ${response.error || 'Unknown error'}`, 'error');
        }
        
        // Scroll to results
        setTimeout(() => {
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        }, 500);
        
        // Reset the form
        processingComplete = true;
        updateUploadButton();
    }
    
    function createSummaryCards(successful, failed) {
        const total = successful + failed;
        
        // Success card
        const successCard = document.createElement('div');
        successCard.className = 'summary-card success';
        successCard.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-semibold text-green-800">Successful</h4>
                    <p class="text-2xl font-bold text-green-600">${successful}</p>
                </div>
                <div class="bg-green-100 p-3 rounded-full">
                    <i class="fas fa-check-circle text-green-600 text-2xl"></i>
                </div>
            </div>
            <div class="mt-2 text-sm text-green-600">
                ${total > 0 ? Math.round((successful / total) * 100) : 0}% success rate
            </div>
        `;
        resultsSummary.appendChild(successCard);
        
        // Error card
        const errorCard = document.createElement('div');
        errorCard.className = 'summary-card error';
        errorCard.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-semibold text-red-800">Failed</h4>
                    <p class="text-2xl font-bold text-red-600">${failed}</p>
                </div>
                <div class="bg-red-100 p-3 rounded-full">
                    <i class="fas fa-times-circle text-red-600 text-2xl"></i>
                </div>
            </div>
            <div class="mt-2 text-sm text-red-600">
                ${total > 0 ? Math.round((failed / total) * 100) : 0}% failure rate
            </div>
        `;
        resultsSummary.appendChild(errorCard);
        
        // Total card
        const totalCard = document.createElement('div');
        totalCard.className = 'summary-card info';
        totalCard.innerHTML = `
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="font-semibold text-blue-800">Total Files</h4>
                    <p class="text-2xl font-bold text-blue-600">${total}</p>
                </div>
                <div class="bg-blue-100 p-3 rounded-full">
                    <i class="fas fa-file-alt text-blue-600 text-2xl"></i>
                </div>
            </div>
            <div class="mt-2 text-sm text-blue-600">
                Processing completed
            </div>
        `;
        resultsSummary.appendChild(totalCard);
    }
    
    function createResultCard(type, file) {
        const card = document.createElement('div');
        card.className = `result-card result-${type} slide-up`;
        
        if (type === 'success') {
            const fileName = file.file_path.split('/').pop();
            card.innerHTML = `
                <div class="flex items-start">
                    <div class="bg-green-100 p-2 rounded-lg mr-4">
                        <i class="fas fa-check-circle text-green-600 text-xl"></i>
                    </div>
                    <div class="flex-1">
                        <h3 class="font-semibold text-gray-800 mb-1">${fileName}</h3>
                        <p class="text-sm text-green-600 mb-3">Processed successfully</p>
                        <div class="bg-gray-50 rounded-lg p-3">
                            <button class="text-blue-600 hover:text-blue-800 text-sm font-medium" onclick="toggleResult('result-${fileName.replace(/[^a-zA-Z0-9]/g, '_')}')">
                                <i class="fas fa-eye mr-1"></i>
                                View Results
                            </button>
                            <div id="result-${fileName.replace(/[^a-zA-Z0-9]/g, '_')}" class="hidden mt-3">
                                <pre class="whitespace-pre-wrap text-xs bg-gray-800 text-gray-100 p-3 rounded overflow-x-auto">${JSON.stringify(file.result, null, 2)}</pre>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            card.innerHTML = `
                <div class="flex items-start">
                    <div class="bg-red-100 p-2 rounded-lg mr-4">
                        <i class="fas fa-times-circle text-red-600 text-xl"></i>
                    </div>
                    <div class="flex-1">
                        <h3 class="font-semibold text-gray-800 mb-1">${file.file_path || 'Unknown file'}</h3>
                        <p class="text-sm text-red-600">Error: ${file.error || 'Unknown error'}</p>
                    </div>
                </div>
            `;
        }
        
        return card;
    }
    
    function toggleResult(resultId) {
        const resultElement = document.getElementById(resultId);
        if (resultElement) {
            resultElement.classList.toggle('hidden');
        }
    }
    
    function downloadResultsFile() {
        // Create a text file with all results
        let content = 'MetaMed Research Paper Rater - Processing Results\n';
        content += `Generated: ${new Date().toLocaleString()}\n`;
        content += '=' .repeat(50) + '\n\n';
        
        const resultCards = document.querySelectorAll('.result-card');
        resultCards.forEach((card, index) => {
            const title = card.querySelector('h3')?.textContent || `Result ${index + 1}`;
            const isSuccess = card.classList.contains('result-success');
            
            content += `${index + 1}. ${title}\n`;
            content += `Status: ${isSuccess ? 'SUCCESS' : 'FAILED'}\n`;
            
            if (!isSuccess) {
                const errorText = card.querySelector('.text-red-600')?.textContent || '';
                content += `Error: ${errorText}\n`;
            }
            
            content += '\n' + '-'.repeat(30) + '\n\n';
        });
        
        // Download the file
        const blob = new Blob([content], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `metamed-results-${new Date().toISOString().split('T')[0]}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification('Results downloaded successfully', 'success');
    }
    
    function startNewUpload() {
        resetForm();
        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    // Make toggleResult globally available
    window.toggleResult = toggleResult;
});
