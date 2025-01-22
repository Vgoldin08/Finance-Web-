// Global chart variable
let categoryChart = null;

// Add this at the beginning of the file
document.getElementById('bankStatement').addEventListener('change', function(e) {
    const fileName = e.target.files[0] ? e.target.files[0].name : 'Choose File';
    document.getElementById('fileNameDisplay').textContent = fileName;
    console.log('File selected:', fileName);
});

// Add input validation
function validateFile(file) {
    console.log('Validando arquivo:', file.name, file.type, file.size);
    const maxSize = 16 * 1024 * 1024; // 16MB
    const allowedTypes = ['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
    
    if (!file) {
        throw new Error('Por favor, selecione um arquivo');
    }
    
    if (!allowedTypes.includes(file.type)) {
        throw new Error('Tipo de arquivo inválido. Por favor, faça upload apenas de arquivos CSV ou XLSX.');
    }
    
    if (file.size > maxSize) {
        throw new Error('Arquivo muito grande (máximo 16MB)');
    }
}

// Add error handling to form submission
document.addEventListener('DOMContentLoaded', () => {
    console.log('Script loaded');
    const form = document.getElementById('uploadForm');
    
    if (!form) {
        console.error('Upload form not found!');
        return;
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log('Form submitted');
        
        const fileInput = document.getElementById('bankStatement');
        const loadingIndicator = document.getElementById('loadingIndicator');
        const errorDisplay = document.getElementById('errorDisplay');
        
        // Clear previous errors and show them if they exist
        errorDisplay.style.display = 'block';
        errorDisplay.textContent = '';
        
        try {
            // Validate file
            if (!fileInput || !fileInput.files || !fileInput.files[0]) {
                throw new Error('Please select a file');
            }

            validateFile(fileInput.files[0]);
            
            // Show loading indicator
            loadingIndicator.style.display = 'block';
            
            const formData = new FormData();
            formData.append('file', fileInput.files[0]);

            console.log('Sending request to server...');
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            
            console.log('Response received:', response.status);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'An error occurred while processing the file');
            }
            
            if (data.error) {
                throw new Error(data.error);
            }
            
            console.log('Processing successful, displaying results');
            displayResults(data);
            
        } catch (error) {
            console.error('Error during processing:', error);
            errorDisplay.textContent = error.message;
            document.querySelector('.results-section').style.display = 'none';
        } finally {
            loadingIndicator.style.display = 'none';
        }
    });
});

// Add input sanitization to displayResults
function sanitizeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function displayResults(data) {
    document.querySelector('.results-section').style.display = 'block';
    
    // Display financial summary
    displayFinancialSummary(data);
    
    // Display categories
    displayCategories(data.categories);
    
    // Display category analysis
    displayCategoryAnalysis(data);
    
    // Display spending patterns
    displaySpendingPatterns(data);
    
    // Display transaction analysis
    displayTransactionAnalysis(data);
    
    // Display recommendations
    displayRecommendations(data.recommendations);
    
    // Create charts
    createCharts(data);
}

function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(Math.abs(value));
}

function displayFinancialSummary(data) {
    const summaryItems = {
        totalSpent: {
            label: 'Total Gasto',
            value: data.total_spent,
            icon: 'fa-minus-circle',
            class: 'negative'
        },
        totalReceived: {
            label: 'Total Recebido',
            value: data.total_received,
            icon: 'fa-plus-circle',
            class: 'positive'
        },
        netBalance: {
            label: 'Saldo',
            value: data.net_balance,
            icon: 'fa-balance-scale',
            class: data.net_balance >= 0 ? 'positive' : 'negative'
        }
    };

    Object.entries(summaryItems).forEach(([id, item]) => {
        document.getElementById(id).innerHTML = `
            <div class="summary-content ${item.class}">
                <i class="fas ${item.icon}"></i>
                <div class="summary-details">
                    <span class="summary-label">${item.label}</span>
                    <span class="summary-value">${formatCurrency(item.value)}</span>
                </div>
            </div>
        `;
    });
}

function displayCategories(categories) {
    const categoryList = Object.entries(categories)
        .sort((a, b) => b[1] - a[1])
        .map(([category, amount]) => `
            <div class="category-item">
                <span class="category-name">
                    <i class="fas fa-tag"></i> ${category.charAt(0).toUpperCase() + category.slice(1)}
                </span>
                <span class="category-amount">${formatCurrency(amount)}</span>
            </div>
        `)
        .join('');
    
    document.getElementById('categoryBreakdown').innerHTML = categoryList;
}

function displayCategoryAnalysis(data) {
    const topCategories = document.getElementById('topCategories');
    topCategories.innerHTML = `
        <h4>Principais Categorias de Gastos</h4>
        <div class="insight-content">
            ${data.insights.filter(insight => 
                insight.includes('Principais categorias de gastos') ||
                (insight.includes('- ') && insight.includes('%'))
            ).join('<br>') || 'Nenhum dado de categoria disponível'}
        </div>
    `;
    
    const categoryAlerts = document.getElementById('categoryAlerts');
    const alertsContent = data.insights
        .filter(insight => insight.includes('Alerta de gasto alto'))
        .map(alert => `<div class="alert alert-warning">${alert}</div>`)
        .join('');
    
    categoryAlerts.innerHTML = `
        <h4>Alertas de Categoria</h4>
        <div class="insight-content">
            ${alertsContent || 'Nenhum alerta no momento'}
        </div>
    `;
}

function displaySpendingPatterns(data) {
    // Weekly trends
    const weeklyTrends = document.getElementById('weeklyTrends');
    weeklyTrends.innerHTML = `
        <h4>Weekly Trends</h4>
        ${data.insights.filter(insight => insight.includes('trending')).join('<br>')}
    `;
    
    // Daily patterns
    const dailyPatterns = document.getElementById('dailyPatterns');
    dailyPatterns.innerHTML = `
        <h4>Daily Patterns</h4>
        ${data.insights.filter(insight => insight.includes('spending day')).join('<br>')}
    `;
}

function displayTransactionAnalysis(data) {
    // Frequent places
    const frequentPlaces = document.getElementById('frequentPlaces');
    let frequentPlacesContent = '';
    
    // Find the "Most frequent places" section and its following items
    let collectingFrequent = false;
    data.insights.forEach(insight => {
        if (insight.includes('Most frequent places:')) {
            collectingFrequent = true;
            frequentPlacesContent += `<p>${insight}</p>`;
        } else if (collectingFrequent && insight.startsWith('- ')) {
            frequentPlacesContent += `<p class="place-item">${insight}</p>`;
        } else if (collectingFrequent && !insight.startsWith('- ')) {
            collectingFrequent = false;
        }
    });

    frequentPlaces.innerHTML = `
        <h4>Most Frequent Places</h4>
        <div class="insight-content">
            ${frequentPlacesContent || 'No frequent places data available'}
        </div>
    `;
    
    // Large expenses
    const largeExpenses = document.getElementById('largeExpenses');
    let largeExpensesContent = '';
    
    // Find the "Largest expenses" section and its following items
    let collectingExpenses = false;
    data.insights.forEach(insight => {
        if (insight.includes('Largest expenses:')) {
            collectingExpenses = true;
            largeExpensesContent += `<p>${insight}</p>`;
        } else if (collectingExpenses && insight.startsWith('- ')) {
            largeExpensesContent += `<p class="expense-item">${insight}</p>`;
        } else if (collectingExpenses && !insight.startsWith('- ')) {
            collectingExpenses = false;
        }
    });

    largeExpenses.innerHTML = `
        <h4>Largest Expenses</h4>
        <div class="insight-content">
            ${largeExpensesContent || 'No large expenses data available'}
        </div>
    `;
}

function formatCategory(category) {
    return category.charAt(0).toUpperCase() + category.slice(1);
}

function createCharts(data) {
    const ctx = document.getElementById('categoryChart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (categoryChart !== null) {
        categoryChart.destroy();
    }
    
    const categories = Object.keys(data.categories);
    const amounts = Object.values(data.categories);
    
    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: categories.map(formatCategory),
            datasets: [{
                data: amounts,
                backgroundColor: [
                    '#3b82f6',
                    '#10b981',
                    '#f59e0b',
                    '#ef4444',
                    '#8b5cf6',
                    '#ec4899',
                    '#6366f1'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right'
                }
            }
        }
    });
}

function displayRecommendations(recommendations) {
    const recommendationsList = document.getElementById('recommendationsList');
    recommendationsList.innerHTML = recommendations.map(rec => `
        <li class="recommendation-card priority-${rec.priority}">
            <div class="recommendation-header">
                <span class="recommendation-title">${rec.title}</span>
                <span class="priority-badge">${rec.priority}</span>
            </div>
            <p class="recommendation-description">${rec.description}</p>
            <div class="recommendation-actions">
                <h4>Suggested Actions:</h4>
                <ul>
                    ${rec.actions.map(action => `
                        <li><i class="fas fa-check-circle"></i> ${action}</li>
                    `).join('')}
                </ul>
            </div>
        </li>
    `).join('');
} 