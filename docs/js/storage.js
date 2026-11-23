/**
 * Local Storage Management Service
 * Persists user solved status, bookmarked problems, and view preferences.
 */

const STORAGE_KEYS = {
  SOLVED_IDS: 'dsa_solved_problem_ids',
  BOOKMARKED_IDS: 'dsa_bookmarked_problem_ids',
  PAGE_SIZE: 'dsa_page_size',
};

class StorageService {
  /**
   * Retrieves the set of problem IDs marked as solved.
   * @returns {Set<string>}
   */
  getSolvedIds() {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.SOLVED_IDS);
      return data ? new Set(JSON.parse(data)) : new Set();
    } catch (err) {
      console.warn('StorageService: Failed to parse solved IDs', err);
      return new Set();
    }
  }

  /**
   * Saves solved problem IDs.
   * @param {Set<string>} ids
   */
  saveSolvedIds(ids) {
    try {
      localStorage.setItem(STORAGE_KEYS.SOLVED_IDS, JSON.stringify(Array.from(ids)));
    } catch (err) {
      console.error('StorageService: Failed to persist solved IDs', err);
    }
  }

  /**
   * Toggles solved state for a given problem ID.
   * @param {string} id 
   * @returns {boolean} true if now solved, false if unsolved
   */
  toggleSolved(id) {
    const ids = this.getSolvedIds();
    let isSolved = false;
    if (ids.has(id)) {
      ids.delete(id);
    } else {
      ids.add(id);
      isSolved = true;
    }
    this.saveSolvedIds(ids);
    return isSolved;
  }

  /**
   * Retrieves bookmarked problem IDs.
   * @returns {Set<string>}
   */
  getBookmarkedIds() {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.BOOKMARKED_IDS);
      return data ? new Set(JSON.parse(data)) : new Set();
    } catch (err) {
      console.warn('StorageService: Failed to parse bookmarked IDs', err);
      return new Set();
    }
  }

  /**
   * Saves bookmarked problem IDs.
   * @param {Set<string>} ids
   */
  saveBookmarkedIds(ids) {
    try {
      localStorage.setItem(STORAGE_KEYS.BOOKMARKED_IDS, JSON.stringify(Array.from(ids)));
    } catch (err) {
      console.error('StorageService: Failed to persist bookmarked IDs', err);
    }
  }

  /**
   * Toggles bookmark state for a given problem ID.
   * @param {string} id 
   * @returns {boolean} true if now bookmarked, false if unbookmarked
   */
  toggleBookmark(id) {
    const ids = this.getBookmarkedIds();
    let isBookmarked = false;
    if (ids.has(id)) {
      ids.delete(id);
    } else {
      ids.add(id);
      isBookmarked = true;
    }
    this.saveBookmarkedIds(ids);
    return isBookmarked;
  }

  /**
   * Gets preferred page size.
   * @param {number|string} defaultSize 
   * @returns {number|string}
   */
  getPageSize(defaultSize = 30) {
    try {
      const val = localStorage.getItem(STORAGE_KEYS.PAGE_SIZE);
      if (val === 'ALL') return 'ALL';
      const parsed = parseInt(val, 10);
      return !isNaN(parsed) && parsed > 0 ? parsed : defaultSize;
    } catch {
      return defaultSize;
    }
  }

  /**
   * Sets preferred page size.
   * @param {number|string} size 
   */
  setPageSize(size) {
    try {
      localStorage.setItem(STORAGE_KEYS.PAGE_SIZE, String(size));
    } catch (err) {
      console.warn('StorageService: Failed to save page size', err);
    }
  }
}

export const storageService = new StorageService();
