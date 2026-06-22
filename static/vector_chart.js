window.addEventListener('load', function() {
    const canvas = document.getElementById('vectorRadarChart');
    if (!canvas) return;

    // 0.0 ~ 1.0 데이터를 0 ~ 100 퍼센트 수치로 변환
    const rawData = JSON.parse(canvas.getAttribute('data-vector'));
    const vectorData = rawData.map(v => Math.round(v * 100));

    // 다크모드 감지 (장고 어드민 수동 토글 지원 + 브라우저 OS 설정 기준)
    const htmlTheme = document.documentElement.getAttribute('data-theme');
    const isOsDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDarkMode = htmlTheme === 'dark' || (htmlTheme !== 'light' && isOsDark);

    const textColor = isDarkMode ? '#E5E7EB' : '#4B5563'; // 다크모드면 밝은회색, 아니면 진한회색
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.15)' : 'rgba(0, 0, 0, 0.08)';

    new Chart(canvas, {
        type: 'radar',
        data: {
            labels: ['활동성', '계획성', '사교성', '공간지향', '경험지향', '소비지향'],
            datasets: [{
                label: '성향 매칭률',
                data: vectorData,
                backgroundColor: 'rgba(99, 102, 241, 0.35)',
                borderColor: 'rgba(129, 140, 248, 1)', // 선을 조금 더 밝고 선명하게
                borderWidth: 2.5,
                pointBackgroundColor: isDarkMode ? '#1e1e2f' : '#ffffff',
                pointBorderColor: 'rgba(129, 140, 248, 1)',
                pointBorderWidth: 2.5,
                pointRadius: 4,
                pointHoverRadius: 6,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(17, 24, 39, 0.9)',
                    titleFont: { size: 14, family: 'sans-serif' },
                    bodyFont: { size: 15, family: 'sans-serif', weight: 'bold' },
                    padding: 12,
                    cornerRadius: 8,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return ' ' + context.raw + '%'; // 툴팁에도 퍼센트 표시
                        }
                    }
                }
            },
            scales: {
                r: {
                    angleLines: {
                        display: true,
                        color: gridColor
                    },
                    grid: {
                        color: gridColor
                    },
                    pointLabels: {
                        font: {
                            size: 13,
                            weight: 'bold',
                            family: 'sans-serif'
                        },
                        color: textColor,
                        // 외곽 꼭짓점 라벨에 퍼센트 수치 표시
                        callback: function(label, index) {
                            return label + ' ' + vectorData[index] + '%';
                        }
                    },
                    ticks: {
                        display: false,
                        stepSize: 25,
                        min: 0,
                        max: 100
                    }
                }
            }
        }
    });
});
