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
        
        if (filesToUpload.length === 0) {
            fileList.innerHTML = `
                <div class="text-center py-8 text-gray-400">
                    <i class="fas fa-inbox text-4xl mb-2"></i>
                    <p>No files selected yet</p>
                </div>
            `;
            return;
        }
        
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
            // Store all results for pagination
            window.allResults = [];
            
            // Collect successful uploads
            if (response.data && response.data.results && response.data.results.successful) {
                response.data.results.successful.forEach(file => {
                    window.allResults.push({
                        type: 'success',
                        data: file
                    });
                });
            }
            
            // Collect failed uploads
            if (response.data && response.data.results && response.data.results.failed) {
                response.data.results.failed.forEach(file => {
                    window.allResults.push({
                        type: 'error',
                        data: file
                    });
                });
            }
            
            // Initialize pagination
            window.currentPage = 1;
            window.resultsPerPage = 1;
            
            // Create pagination controls
            createPaginationControls();
            
            // Display first page
            displayResultsPage();
            
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

    function createPaginationControls() {
        const totalPages = Math.ceil(window.allResults.length / window.resultsPerPage);
        
        if (totalPages <= 1) return;
        
        const paginationContainer = document.createElement('div');
        paginationContainer.className = 'flex justify-center items-center space-x-4 mt-8';
        paginationContainer.innerHTML = `
            <button id="prev-btn" class="px-4 py-2 bg-gray-200 text-gray-600 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors" ${window.currentPage === 1 ? 'disabled' : ''}>
                <i class="fas fa-chevron-left mr-2"></i>Previous
            </button>
            <div class="flex space-x-2">
                ${Array.from({length: totalPages}, (_, i) => i + 1).map(page => `
                    <button class="page-btn px-3 py-1 rounded-lg transition-colors ${page === window.currentPage ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'}" data-page="${page}">
                        ${page}
                    </button>
                `).join('')}
            </div>
            <button id="next-btn" class="px-4 py-2 bg-gray-200 text-gray-600 rounded-lg hover:bg-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors" ${window.currentPage === totalPages ? 'disabled' : ''}>
                Next<i class="fas fa-chevron-right ml-2"></i>
            </button>
        `;
        
        resultsContainer.appendChild(paginationContainer);
        
        // Add event listeners
        document.getElementById('prev-btn').addEventListener('click', () => {
            if (window.currentPage > 1) {
                window.currentPage--;
                displayResultsPage();
            }
        });
        
        document.getElementById('next-btn').addEventListener('click', () => {
            const totalPages = Math.ceil(window.allResults.length / window.resultsPerPage);
            if (window.currentPage < totalPages) {
                window.currentPage++;
                displayResultsPage();
            }
        });
        
        document.querySelectorAll('.page-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                window.currentPage = parseInt(e.target.getAttribute('data-page'));
                displayResultsPage();
            });
        });
    }

    function displayResultsPage() {
        // Clear existing results
        const existingCards = resultsContainer.querySelectorAll('.result-card');
        existingCards.forEach(card => card.remove());
        
        // Clear existing pagination
        const existingPagination = resultsContainer.querySelectorAll('button');
        existingPagination.forEach(btn => btn.remove());
        
        const startIndex = (window.currentPage - 1) * window.resultsPerPage;
        const endIndex = startIndex + window.resultsPerPage;
        const currentResults = window.allResults.slice(startIndex, endIndex);
        
        currentResults.forEach(result => {
            if (result.type === 'success') {
                createSuccessCard(result.data);
            } else {
                createErrorCard(result.data);
            }
        });
        
        // Recreate pagination controls
        createPaginationControls();
    }

    function createSuccessCard(file) {
        const resultData = file.result;
        const scores = resultData.scores || [];
        const metadata = resultData.metadata || {};
        
        const resultCard = document.createElement('div');
        resultCard.className = 'result-card result-success';
        resultCard.innerHTML = `
            <div class="mb-6">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center">
                        <div class="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mr-4">
                            <i class="fas fa-check-circle text-green-600 text-xl"></i>
                        </div>
                        <div>
                            <h3 class="text-xl font-bold text-gray-800">${file.file_path.split('/').pop()}</h3>
                            <p class="text-sm text-green-600 font-medium">Processed successfully</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <div class="text-2xl font-bold text-green-600">${metadata.total_score || 0}</div>
                        <div class="text-sm text-gray-500">Total Score</div>
                    </div>
                </div>
            </div>
            
            <!-- Score Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                ${scores.map(score => `
                    <div class="bg-white rounded-lg p-4 border border-gray-200 hover:shadow-md transition-shadow">
                        <div class="flex items-center justify-between mb-2">
                            <h4 class="font-semibold text-gray-800 text-sm">${score.category}</h4>
                            <div class="flex items-center">
                                <div class="w-8 h-8 rounded-full flex items-center justify-center ${getScoreColor(score.score)}">
                                    <span class="text-white font-bold text-xs">${score.score}</span>
                                </div>
                            </div>
                        </div>
                        <p class="text-xs text-gray-600 leading-relaxed">${score.rationale}</p>
                    </div>
                `).join('')}
            </div>
            
            <!-- Metadata Section -->
            <div class="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-4">
                <h4 class="font-semibold text-gray-800 mb-3 flex items-center">
                    <i class="fas fa-info-circle text-blue-600 mr-2"></i>
                    Analysis Summary
                </h4>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <div class="text-sm text-gray-600 mb-1">Confidence Level</div>
                        <div class="flex items-center">
                            <div class="w-full bg-gray-200 rounded-full h-2 mr-2">
                                <div class="bg-blue-600 h-2 rounded-full" style="width: ${(metadata.confidence || 0) * 100}%"></div>
                            </div>
                            <span class="text-sm font-medium">${Math.round((metadata.confidence || 0) * 100)}%</span>
                        </div>
                    </div>
                    <div>
                        <div class="text-sm text-gray-600 mb-1">Paper Type</div>
                        <div class="text-sm font-medium text-gray-800 capitalize">${metadata.paper_type || 'Unknown'}</div>
                    </div>
                </div>
                
                ${metadata.comments && metadata.comments.length > 0 ? `
                    <div class="mt-4">
                        <div class="text-sm text-gray-600 mb-2">Key Comments</div>
                        <ul class="space-y-1">
                            ${metadata.comments.map(comment => `
                                <li class="text-sm text-gray-700 flex items-start">
                                    <i class="fas fa-chevron-right text-blue-500 text-xs mr-2 mt-1"></i>
                                    <span>${comment}</span>
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}
                
                ${metadata.keywords && metadata.keywords.length > 0 ? `
                    <div class="mt-4">
                        <div class="text-sm text-gray-600 mb-2">Keywords</div>
                        <div class="flex flex-wrap gap-2">
                            ${metadata.keywords.map(keyword => `
                                <span class="px-2 py-1 bg-white rounded-full text-xs font-medium text-gray-700 border border-gray-300">
                                    ${keyword}
                                </span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
        resultsContainer.appendChild(resultCard);
    }

    function createErrorCard(file) {
        const resultCard = document.createElement('div');
        resultCard.className = 'result-card result-error';
        resultCard.innerHTML = `
            <div class="flex items-start">
                <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mr-4">
                    <i class="fas fa-times-circle text-red-600 text-xl"></i>
                </div>
                <div>
                    <h3 class="text-xl font-bold text-gray-800">${file.file_path || 'Unknown file'}</h3>
                    <p class="text-sm text-red-500 mt-1">Error: ${file.error || 'Unknown error'}</p>
                </div>
            </div>
        `;
        resultsContainer.appendChild(resultCard);
    }

    function getScoreColor(score) {
        if (score >= 8) return 'bg-green-500';
        if (score >= 6) return 'bg-yellow-500';
        if (score >= 4) return 'bg-orange-500';
        return 'bg-red-500';
    }
});
