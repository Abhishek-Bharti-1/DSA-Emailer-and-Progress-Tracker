/**
 * Chart Visualization Service
 * Encapsulates Chart.js instances and themes for metrics visualizations.
 */

import { CONFIG } from './config.js';

class ChartService {
  constructor() {
    this.difficultyChart = null;
    this.topicsChart = null;
  }

  /**
   * Renders or updates the difficulty doughnut chart.
   * @param {HTMLCanvasElement} canvas
   * @param {{ Easy: number, Medium: number, Hard: number }} counts
   */
  renderDifficultyChart(canvas, counts) {
    if (!canvas) return;

    if (this.difficultyChart) {
      this.difficultyChart.destroy();
      this.difficultyChart = null;
    }

    const { Easy = 0, Medium = 0, Hard = 0 } = counts;
    const total = Easy + Medium + Hard;
    const hasData = total > 0;

    const data = hasData ? [Easy, Medium, Hard] : [1, 1, 1];
    const bgColors = hasData
      ? [
          CONFIG.themes.difficulties.Easy.chartColor,
          CONFIG.themes.difficulties.Medium.chartColor,
          CONFIG.themes.difficulties.Hard.chartColor,
        ]
      : ['#374151', '#4b5563', '#1f2937'];

    this.difficultyChart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: ['Easy', 'Medium', 'Hard'],
        datasets: [
          {
            data,
            backgroundColor: bgColors,
            borderColor: '#111827',
            borderWidth: 3,
            hoverOffset: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '72%',
        plugins: {
          legend: { display: false },
          tooltip: {
            enabled: hasData,
            callbacks: {
              label: (ctx) => ` ${ctx.label}: ${ctx.raw} problems (${Math.round((ctx.raw / total) * 100)}%)`,
            },
          },
        },
      },
    });
  }

  /**
   * Renders or updates the topic horizontal bar chart.
   * @param {HTMLCanvasElement} canvas
   * @param {Record<string, number>} topicCounts
   * @param {number} maxTopics
   */
  renderTopicsChart(canvas, topicCounts, maxTopics = 8) {
    if (!canvas) return;

    if (this.topicsChart) {
      this.topicsChart.destroy();
      this.topicsChart = null;
    }

    const sorted = Object.entries(topicCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, maxTopics);

    const labels = sorted.map(([topic]) => topic);
    const data = sorted.map(([, count]) => count);

    this.topicsChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Problems',
            data,
            backgroundColor: '#6366f1',
            hoverBackgroundColor: '#818cf8',
            borderRadius: 6,
            barThickness: 16,
          },
        ],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => ` ${ctx.raw} problem${ctx.raw === 1 ? '' : 's'}`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: '#1f2937' },
            ticks: { color: '#9ca3af', precision: 0 },
          },
          y: {
            grid: { display: false },
            ticks: { color: '#d1d5db', font: { size: 12 } },
          },
        },
      },
    });
  }

  /**
   * Destroys all active chart instances.
   */
  destroyAll() {
    if (this.difficultyChart) {
      this.difficultyChart.destroy();
      this.difficultyChart = null;
    }
    if (this.topicsChart) {
      this.topicsChart.destroy();
      this.topicsChart = null;
    }
  }
}

export const chartService = new ChartService();
