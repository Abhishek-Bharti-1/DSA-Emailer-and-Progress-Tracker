/**
 * Firebase Firestore Data Service
 * Modular client for fetching sent problems and progress state.
 */

import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js';
import {
  getFirestore,
  collection,
  getDocs,
  doc,
  getDoc,
} from 'https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js';
import { CONFIG } from './config.js';

export class FirebaseService {
  constructor() {
    this.app = null;
    this.db = null;
    this.isConnected = false;
  }

  /**
   * Initializes the Firebase client.
   * @param {Object} customConfig Optional override
   */
  init(customConfig = null) {
    const cfg = customConfig || CONFIG.firebase;
    if (!cfg.projectId || cfg.projectId === 'YOUR_PROJECT_ID') {
      throw new Error('PROJECT_ID_NOT_CONFIGURED');
    }

    const firebaseConfig = {
      projectId: cfg.projectId,
      ...(cfg.apiKey ? { apiKey: cfg.apiKey } : {}),
    };

    // Use a unique app name to prevent re-initialization errors
    const appName = `dsa-app-${cfg.projectId}`;
    this.app = initializeApp(firebaseConfig, appName);
    this.db = getFirestore(this.app);
    this.isConnected = true;
    return this.db;
  }

  /**
   * Fetches sent problems and progress state from Firestore.
   * @returns {Promise<{ problems: Array<Object>, progress: Object|null }>}
   */
  async fetchLiveState() {
    if (!this.db) {
      this.init();
    }

    const sentRef = collection(this.db, CONFIG.firestorePaths.sentProblems);
    const progressDocRef = doc(this.db, ...CONFIG.firestorePaths.progressDoc);

    const [problemsSnap, progressSnap] = await Promise.all([
      getDocs(sentRef),
      getDoc(progressDocRef).catch(() => null),
    ]);

    const problems = problemsSnap.docs.map((docSnap) => {
      const data = docSnap.data();
      return this._normalizeProblem(data, docSnap.id);
    });

    const progress = progressSnap && progressSnap.exists ? progressSnap.data() : null;

    return { problems, progress };
  }

  /**
   * Loads static fallback data from JSON files.
   * @returns {Promise<{ problems: Array<Object>, progress: Object|null }>}
   */
  async fetchFallbackData() {
    const [progressRes, sentRes] = await Promise.all([
      fetch(CONFIG.fallbackPaths.progress).catch(() => null),
      fetch(CONFIG.fallbackPaths.sentLog).catch(() => null),
    ]);

    let progress = null;
    let sent = [];

    if (progressRes && progressRes.ok) {
      progress = await progressRes.json();
    }
    if (sentRes && sentRes.ok) {
      sent = await sentRes.json();
    }

    const problems = (sent || []).map((p, idx) =>
      this._normalizeProblem(p, p.id || `entry-${idx}`)
    );

    return { problems, progress };
  }

  /**
   * Normalizes problem schema.
   * @private
   */
  _normalizeProblem(raw, fallbackId) {
    const diffRaw = String(raw.difficulty || '').trim().toLowerCase();
    let difficulty = 'Medium';
    if (diffRaw.includes('easy') || diffRaw.includes('basic')) difficulty = 'Easy';
    else if (diffRaw.includes('hard') || diffRaw.includes('expert')) difficulty = 'Hard';

    return {
      id: String(raw.id || fallbackId || '').trim(),
      title: String(raw.title || 'Untitled Problem').trim(),
      topic: String(raw.topic || 'General').trim(),
      difficulty,
      source: String(raw.source || 'a2z_sheet').trim(),
      url: String(raw.url || '#').trim(),
      platform: String(raw.platform || raw.source || 'DSA').trim(),
      date: String(raw.date || '').split('T')[0].trim(),
      createdAt: raw.created_at || raw.createdAt || '',
    };
  }
}

export const firebaseService = new FirebaseService();
