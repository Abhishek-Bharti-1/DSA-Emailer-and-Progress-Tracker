/**
 * Main Application Orchestrator
 * Connects services, manages state, delegates UI events, and coordinates updates.
 */

import { CONFIG } from './config.js';
import { storageService } from './storage.js';
import { firebaseService } from './firebase.js';
import { chartService } from './charts.js';
import { renderService } from './render.js';

class AppController {
  constructor() {
    this.state = {
      rawProblems: [],
      filteredProblems: [],
      progressData: null,
      solvedIds: new Set(),
      bookmarkedIds: new Set(),
      currentPage: 1,
      pageSize: storageService.getPageSize(CONFIG.pagination.defaultPageSize),
      sortField: 'date',
      sortOrder: 'desc',
      searchQuery: '',
      difficultyFilter: 'ALL',
      topicFilter: 'ALL',
      statusFilter: 'ALL',
    };
  }

  /**
   * Initializes the application.
   */
  async init() {
    this.state.solvedIds = storageService.getSolvedIds();
    this.state.bookmarkedIds = storageService.getBookmarkedIds();

    this._bindDOMEvents();
    await this.loadData();
  }

  /**
   * Loads data from Firestore with fallback to local JSON.
   */
  async loadData() {
    renderService.toggleLoading(true);
    renderService.updateConnectionStatus('loading', 'Connecting...');

    let loaded = false;

    // Try Firestore live fetch first
    try {
      const { problems, progress } = await firebaseService.fetchLiveState();
      this.state.rawProblems = problems;
      this.state.progressData = progress;
      renderService.updateConnectionStatus('live', `Live (Firestore)`);
      loaded = true;
    } catch (err) {
      console.warn('Live Firestore fetch unsuccessful; falling back to local dataset.', err);
    }

    // Fallback if needed
    if (!loaded) {
      try {
        const { problems, progress } = await firebaseService.fetchFallbackData();
        this.state.rawProblems = problems;
        this.state.progressData = progress;
        renderService.updateConnectionStatus('fallback', 'Local Data');
      } catch (fallbackErr) {
        console.error('Failed to load fallback data:', fallbackErr);
      }
    }

    renderService.toggleLoading(false);
    this.renderAll();
  }

  /**
   * Re-renders all components based on current state.
   */
  renderAll() {
    const { rawProblems, progressData, solvedIds, bookmarkedIds } = this.state;

    // 1. KPI Cards
    renderService.updateKPIs({
      problems: rawProblems,
      progress: progressData,
      solvedIds,
      bookmarkedIds,
    });

    // 2. Compute distributions
    const diffCounts = { Easy: 0, Medium: 0, Hard: 0 };
    const topicCounts = {};
    const sourceCounts = {};

    for (const p of rawProblems) {
      if (diffCounts[p.difficulty] !== undefined) {
        diffCounts[p.difficulty]++;
      }
      topicCounts[p.topic] = (topicCounts[p.topic] || 0) + 1;
      sourceCounts[p.source] = (sourceCounts[p.source] || 0) + 1;
    }

    // Update Difficulty Badges Counter
    const countEasy = document.getElementById('countEasy');
    const countMedium = document.getElementById('countMedium');
    const countHard = document.getElementById('countHard');
    if (countEasy) countEasy.textContent = String(diffCounts.Easy);
    if (countMedium) countMedium.textContent = String(diffCounts.Medium);
    if (countHard) countHard.textContent = String(diffCounts.Hard);

    // 3. Charts
    const diffCanvas = document.getElementById('difficultyChart');
    if (diffCanvas) chartService.renderDifficultyChart(diffCanvas, diffCounts);

    const topicCanvas = document.getElementById('topicsChart');
    if (topicCanvas) chartService.renderTopicsChart(topicCanvas, topicCounts, 8);

    const topicTotalElem = document.getElementById('topicCountTotal');
    if (topicTotalElem) {
      topicTotalElem.textContent = `${Object.keys(topicCounts).length} unique topics`;
    }

    // 4. Source Chips
    const sourcesContainer = document.getElementById('sourcesBadges');
    renderService.renderSourceChips(sourcesContainer, sourceCounts);

    // 5. Populate Topic Filter
    const topicSelect = document.getElementById('filterTopic');
    renderService.populateTopicFilter(
      topicSelect,
      Object.keys(topicCounts).sort(),
      this.state.topicFilter
    );

    // 6. Filter & Render Table
    this.applyFiltersAndRenderTable();
  }

  /**
   * Filters, sorts, and renders the problem table.
   */
  applyFiltersAndRenderTable() {
    const {
      rawProblems,
      searchQuery,
      difficultyFilter,
      topicFilter,
      statusFilter,
      sortField,
      sortOrder,
      solvedIds,
      bookmarkedIds,
    } = this.state;

    // Filter
    const filtered = rawProblems.filter((p) => {
      if (searchQuery) {
        const titleMatch = p.title.toLowerCase().includes(searchQuery);
        const topicMatch = p.topic.toLowerCase().includes(searchQuery);
        const idMatch = p.id.toLowerCase().includes(searchQuery);
        if (!titleMatch && !topicMatch && !idMatch) return false;
      }

      if (difficultyFilter !== 'ALL' && p.difficulty !== difficultyFilter) {
        return false;
      }

      if (topicFilter !== 'ALL' && p.topic !== topicFilter) {
        return false;
      }

      if (statusFilter === 'SOLVED' && !solvedIds.has(p.id)) return false;
      if (statusFilter === 'UNSOLVED' && solvedIds.has(p.id)) return false;
      if (statusFilter === 'BOOKMARKED' && !bookmarkedIds.has(p.id)) return false;

      return true;
    });

    // Sort
    const diffWeights = { Easy: 1, Medium: 2, Hard: 3 };
    filtered.sort((a, b) => {
      let cmp = 0;
      if (sortField === 'date') {
        cmp = a.date.localeCompare(b.date);
      } else if (sortField === 'difficulty') {
        cmp = (diffWeights[a.difficulty] || 2) - (diffWeights[b.difficulty] || 2);
      } else if (sortField === 'title') {
        cmp = a.title.localeCompare(b.title);
      }
      return sortOrder === 'asc' ? cmp : -cmp;
    });

    this.state.filteredProblems = filtered;

    // Pagination slice
    const total = filtered.length;
    const pageSize = this.state.pageSize === 'ALL' ? total : this.state.pageSize;
    const totalPages = Math.max(1, Math.ceil(total / (pageSize || 1)));

    if (this.state.currentPage > totalPages) {
      this.state.currentPage = totalPages;
    }

    const start = (this.state.currentPage - 1) * (pageSize || 1);
    const pageItems = this.state.pageSize === 'ALL' ? filtered : filtered.slice(start, start + pageSize);

    // Update Showing Badge
    const showingBadge = document.getElementById('showingCountBadge');
    if (showingBadge) {
      showingBadge.textContent = `Showing ${pageItems.length} of ${filtered.length} (${rawProblems.length} total)`;
    }

    // Render Table
    renderService.renderTable(pageItems, { solvedIds, bookmarkedIds });
    renderService.updatePagination(total, this.state.currentPage, this.state.pageSize);
  }

  /**
   * Binds user interaction events.
   * @private
   */
  _bindDOMEvents() {
    // 1. Refresh Button
    document.getElementById('btnRefresh')?.addEventListener('click', () => {
      this.loadData();
    });

    // 2. Search Input (Debounced)
    let timer;
    document.getElementById('searchInput')?.addEventListener('input', (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        this.state.searchQuery = e.target.value.toLowerCase().trim();
        this.state.currentPage = 1;
        this.applyFiltersAndRenderTable();
      }, 180);
    });

    // 3. Dropdown Filters
    document.getElementById('filterDifficulty')?.addEventListener('change', (e) => {
      this.state.difficultyFilter = e.target.value;
      this.state.currentPage = 1;
      this.applyFiltersAndRenderTable();
    });

    document.getElementById('filterTopic')?.addEventListener('change', (e) => {
      this.state.topicFilter = e.target.value;
      this.state.currentPage = 1;
      this.applyFiltersAndRenderTable();
    });

    document.getElementById('filterStatus')?.addEventListener('change', (e) => {
      this.state.statusFilter = e.target.value;
      this.state.currentPage = 1;
      this.applyFiltersAndRenderTable();
    });

    // 4. Table Sorters
    document.getElementById('thDate')?.addEventListener('click', () => {
      this.state.sortField = 'date';
      this.state.sortOrder = this.state.sortOrder === 'asc' ? 'desc' : 'asc';
      this.applyFiltersAndRenderTable();
    });

    document.getElementById('thDiff')?.addEventListener('click', () => {
      this.state.sortField = 'difficulty';
      this.state.sortOrder = this.state.sortOrder === 'asc' ? 'desc' : 'asc';
      this.applyFiltersAndRenderTable();
    });

    // 5. Page Size Selector
    const pageSizeSelect = document.getElementById('selectPageSize');
    if (pageSizeSelect) {
      pageSizeSelect.value = String(this.state.pageSize);
      pageSizeSelect.addEventListener('change', (e) => {
        const val = e.target.value;
        this.state.pageSize = val === 'ALL' ? 'ALL' : parseInt(val, 10);
        storageService.setPageSize(val);
        this.state.currentPage = 1;
        this.applyFiltersAndRenderTable();
      });
    }

    // 6. Pagination Next/Prev
    document.getElementById('btnPrevPage')?.addEventListener('click', () => {
      if (this.state.currentPage > 1) {
        this.state.currentPage--;
        this.applyFiltersAndRenderTable();
      }
    });

    document.getElementById('btnNextPage')?.addEventListener('click', () => {
      this.state.currentPage++;
      this.applyFiltersAndRenderTable();
    });

    // 7. Event Delegation for Table Clicks (Solves & Bookmarks)
    const tableBody = document.getElementById('problemsTableBody');
    tableBody?.addEventListener('click', (e) => {
      const target = e.target.closest('[data-action]');
      if (!target) return;

      const action = target.getAttribute('data-action');
      const id = target.getAttribute('data-id');
      if (!id) return;

      if (action === 'solve') {
        storageService.toggleSolved(id);
        this.state.solvedIds = storageService.getSolvedIds();
      } else if (action === 'bookmark') {
        storageService.toggleBookmark(id);
        this.state.bookmarkedIds = storageService.getBookmarkedIds();
      }

      // Re-update KPIs and Table
      renderService.updateKPIs({
        problems: this.state.rawProblems,
        progress: this.state.progressData,
        solvedIds: this.state.solvedIds,
        bookmarkedIds: this.state.bookmarkedIds,
      });

      this.applyFiltersAndRenderTable();
    });
  }
}

// Boot application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    window.lucide.createIcons();
  }
  const app = new AppController();
  app.init();
});
