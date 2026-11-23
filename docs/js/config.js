/**
 * Central Configuration for DSA Tracker Dashboard
 */

export const CONFIG = {
  // Your Google Cloud / Firebase Project ID
  // Replace this with your project ID (e.g., "dsa-problems-emailer-xxxx")
  firebase: {
    projectId: "dsa-emailer-prod",
    apiKey: "", // Optional: only if your project enforces client API keys
    databaseId: "(default)",
  },

  // Collections and document paths
  firestorePaths: {
    sentProblems: "sent_problems",
    progressDoc: ["state", "progress"],
  },

  // Fallback local paths (if Firestore is unavailable)
  fallbackPaths: {
    sentLog: "./data/sent_log.json",
    progress: "./data/progress.json",
  },

  // Pagination & Display defaults
  pagination: {
    defaultPageSize: 30,
    pageSizeOptions: [15, 30, 60, "ALL"],
  },

  // Topic & Platform color themes
  themes: {
    difficulties: {
      Easy: {
        bg: "bg-emerald-500/10",
        text: "text-emerald-400",
        border: "border-emerald-500/20",
        chartColor: "#10b981",
      },
      Medium: {
        bg: "bg-amber-500/10",
        text: "text-amber-400",
        border: "border-amber-500/20",
        chartColor: "#f59e0b",
      },
      Hard: {
        bg: "bg-rose-500/10",
        text: "text-rose-400",
        border: "border-rose-500/20",
        chartColor: "#f43f5e",
      },
    },
    sources: {
      a2z_sheet: {
        label: "Striver's A2Z",
        color: "bg-teal-500/10 text-teal-300 border-teal-500/20",
      },
      leetcode: {
        label: "LeetCode",
        color: "bg-amber-500/10 text-amber-300 border-amber-500/20",
      },
      gfg: {
        label: "GeeksforGeeks",
        color: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
      },
      codeforces: {
        label: "Codeforces",
        color: "bg-blue-500/10 text-blue-300 border-blue-500/20",
      },
    },
  },
};
