/**
 * AI-Driven Classroom Engagement Monitoring System
 * Chart.js Configurations
 */

// Color Palette
const chartColors = {
    attentive: '#38ef7d',
    sleepy: '#ff9966',
    distracted: '#f5576c',
    neutral: '#4facfe',
    primary: '#3498db',
    primaryLight: 'rgba(52, 152, 219, 0.1)'
};

// Default Chart Options
const defaultChartOptions = {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
        legend: {
            position: 'bottom',
            labels: {
                padding: 20,
                font: {
                    family: "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif",
                    size: 13
                }
            }
        }
    }
};

/**
 * Initialize Pie Chart for Behavior Distribution
 */
function initPieChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.labels || ['Attentive', 'Sleepy', 'Distracted', 'Neutral'],
            datasets: [{
                data: data.values || [28, 5, 7, 5],
                backgroundColor: [
                    chartColors.attentive,
                    chartColors.sleepy,
                    chartColors.distracted,
                    chartColors.neutral
                ],
                borderWidth: 3,
                borderColor: '#fff',
                hoverBorderWidth: 0
            }]
        },
        options: {
            ...defaultChartOptions,
            cutout: '0%',
            plugins: {
                ...defaultChartOptions.plugins,
                title: {
                    display: true,
                    text: 'Student Behavior Distribution',
                    font: {
                        size: 16,
                        weight: '600'
                    },
                    padding: {
                        bottom: 20
                    }
                }
            }
        }
    });
}

/**
 * Initialize Line Chart for Engagement Over Time
 */
function initLineChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels || ['9:00', '9:30', '10:00', '10:30', '11:00', '11:30'],
            datasets: [{
                label: 'Engagement Percentage',
                data: data.values || [65, 72, 68, 75, 70, 62],
                borderColor: chartColors.primary,
                backgroundColor: chartColors.primaryLight,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: chartColors.primary,
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            ...defaultChartOptions,
            plugins: {
                ...defaultChartOptions.plugins,
                title: {
                    display: true,
                    text: 'Engagement Trend Over Time',
                    font: {
                        size: 16,
                        weight: '600'
                    },
                    padding: {
                        bottom: 20
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.parsed.y + '%';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    min: 40,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        },
                        stepSize: 10
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

/**
 * Initialize Bar Chart for Comparison
 */
function initBarChart(canvasId, data) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels || ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
            datasets: [{
                label: 'Engagement Rate',
                data: data.values || [65, 72, 68, 75, 70],
                backgroundColor: [
                    chartColors.attentive,
                    chartColors.sleepy,
                    chartColors.distracted,
                    chartColors.neutral,
                    chartColors.primary
                ],
                borderWidth: 0,
                borderRadius: 8
            }]
        },
        options: {
            ...defaultChartOptions,
            plugins: {
                ...defaultChartOptions.plugins,
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });
}

/**
 * Update Chart Data Dynamically
 */
function updateChartData(chart, newData) {
    chart.data.datasets[0].data = newData;
    chart.update();
}

/**
 * Destroy Chart Instance
 */
function destroyChart(chart) {
    if (chart) {
        chart.destroy();
    }
}

// Auto-initialize charts if canvas elements exist
document.addEventListener('DOMContentLoaded', function() {
    console.log('AI Classroom Engagement - Charts Initialized');
});

