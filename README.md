# 🧩 DSA Problems Daily Emailer & Progress Tracker

An automated, AI-curated system that emails 4 Data Structures & Algorithms (DSA) problems to your inbox every single morning, accompanied by a **live GitHub Pages Dashboard** to monitor your stats, consistency streaks, and full history of dispatched problems.

Sourced primarily from **Striver's A2Z DSA Sheet** and supplemented by **LeetCode**, **Codeforces**, and **GeeksforGeeks**, it ensures disciplined, structured practice with zero spoilers and guaranteed non-repetition.

---

## ✨ Features

- **4 Problems Daily**: Balanced quota of **1 Easy, 2 Medium, 1 Hard** problem delivered every day.
- **Strict Topic Diversity**: All 4 problems are guaranteed to come from different topics (e.g., Arrays, Dynamic Programming, Trees, Binary Search).
- **Mystery Format (Zero Spoilers)**: Daily emails deliberately hide difficulty, topic tags, and platform names. You solve each problem purely on merit, mirroring real interview environments.
- **A2Z Sheet Priority**: Focuses on Striver's comprehensive A2Z DSA course (~455 problems). Automatically supplements from fallback sources (LeetCode, GFG, Codeforces) when needed.
- **🌐 Live GitHub Pages Dashboard**: Hosted dark-mode web dashboard reading directly from Google Cloud Firestore (or local JSON fallback) in real-time. Includes difficulty distribution charts, topic coverage bars, live search, multi-filter queries, and personal progress tracking (mark solved / bookmark for revision).
- **Weekly Progress Reports**: Automated Sunday progress digest summarizing problems solved, difficulty distributions with visual progress bars, streak metrics, and personalized coaching insights powered by Gemini.
- **Gemini AI Agent**: Driven by Google's `gemini-2.5-flash` with native Function Calling (`google-genai` SDK) to orchestrate curation, delivery, and logging — backed by an automatic, zero-dependency Python fallback if the API is ever unreachable.
- **No Repeated Problems Ever**: Persistent state management tracks every problem ever sent across all platforms via canonical URL slugs, normalized titles, and Firestore atomic transactions.

---

## 🏗️ Architecture

```
                                  ┌─────────────────────────────┐
                                  │      Problem Sources        │
                                  ├─────────────────────────────┤
                                  │ • Striver A2Z Sheet Scraper │
                                  │ • LeetCode GraphQL API      │
                                  │ • Codeforces REST API       │
                                  │ • GeeksforGeeks Curated Set │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │ Deduplication & Caching     │
                                  │ (Slug & Title Normalization)│
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    data/problem_cache.json  │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────┐   ┌─────────────────────────┐
│ Cloud Run / GitHub Actions / CLI│──>│ Gemini AI Agent / Router│
│ (Cron: 8:00 AM IST Daily)       │   │ (Function Calling Loop) │
└─────────────────────────────────┘   └──────────┬──────────────┘
                                                 │
                                                 ▼
                                      ┌─────────────────────────┐
                                      │  Intelligent Selector   │
                                      │ (1E, 2M, 1H + 4 Topics) │
                                      └──────────┬──────────────┘
                                                 │
                                                 ▼
                                      ┌─────────────────────────┐
                                      │ Responsive HTML Mailer  │
                                      │(STARTTLS via Gmail SMTP)│
                                      └──────────┬──────────────┘
                                                 │
                                                 ▼
                      ┌─────────────────────────────────────────────────────┐
                      │                 Persistent State                    │
                      ├──────────────────────────┬──────────────────────────┤
                      │ Cloud Firestore          │ Local Git Storage        │
                      │ • sent_problems          │ • data/sent_log.json     │
                      │ • state/progress         │ • data/progress.json     │
                      └────────────┬─────────────┴─────────────┬────────────┘
                                   │                           │
                                   └─────────────┬─────────────┘
                                                 │ (Direct real-time fetch)
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │   GitHub Pages Dashboard    │
                                  │          (/docs)            │
                                  │ • Live Streak & Analytics   │
                                  │ • Difficulty & Topic Charts │
                                  │ • Filterable Question Table │
                                  │ • Solved & Bookmark Tracker │
                                  └─────────────────────────────┘
```

### Problem Flow
1. **Fetch & Cache**: Fetchers extract problems from all 4 sources and normalize them into a unified schema across 19 standard topics.
2. **Deduplicate**: Cross-platform duplicates are eliminated by matching URL slugs and normalized titles, retaining the highest-priority source version (`a2z_sheet` > `leetcode` > `gfg` > `codeforces`).
3. **Select**: The selector filters out previously sent problem IDs, prioritizes A2Z Sheet candidates, and runs depth-first backtracking to pick 1 Easy, 2 Medium, and 1 Hard problem from 4 distinct topics.
4. **Dispatch**: The email builder renders a mobile-responsive dark navy template and sends it via Gmail SMTP with a plain-text fallback.
5. **Persist**: The sent problems are atomically logged, streaks and progress metrics are recalculated in Firestore (or local state files), and synced to the live dashboard.

---

## 🌐 Live GitHub Pages Dashboard

The repository includes a modern, client-side dashboard hosted completely free on **GitHub Pages** (inside the `/docs` folder). It connects directly to your Google Cloud Firestore database in real-time, requiring zero backend servers or changes to your Cloud Run deployment.

### 🌟 Dashboard Features
- **🔥 Current Streak & Consistency**: Tracks consecutive daily problem deliveries.
- **📊 Interactive Visualizations**:
  - **Difficulty Donut Chart**: Proportional breakdown of Easy, Medium, and Hard problems.
  - **Topic Coverage Bar Chart**: Frequency graph of all algorithmic topics covered to date.
- **🎯 Striver's A2Z Sheet Progress**: Visual progress bar tracking overall completion ($X / 455$).
- **📋 Searchable & Filterable Directory**:
  - Live search by problem title, topic, or problem ID.
  - Filter by difficulty (`Easy`, `Medium`, `Hard`).
  - Filter by topic (`Arrays`, `DP`, `Graphs`, `Trees`, etc.).
  - Filter by status (`All`, `Solved`, `Unsolved`, `Bookmarked`).
  - Sort by Date (newest/oldest) and Difficulty (Easy $\to$ Hard or Hard $\to$ Easy).
  - External links opening the problem directly on LeetCode, GFG, Codeforces, or TakeUforward.
- **✅ Personal Solving & Bookmark Tracker**:
  - Mark problems as completed with a single click (persisted in browser `localStorage`).
  - Bookmark challenging questions with ⭐ for future revision.
- **🛡️ Graceful Offline Fallback**: If Firestore is unreachable, the dashboard automatically loads bundled local JSON datasets.

### 📁 Modular Architecture (`docs/`)
The dashboard is built with vanilla ES modules, Tailwind CSS, Chart.js, and Lucide icons following clean software engineering principles:

```
docs/
├── index.html            # Semantic dark-mode Single Page Application
├── data/                 # Offline / fallback JSON snapshots
│   ├── progress.json
│   └── sent_log.json
└── js/
    ├── config.js         # Central configuration (Project ID, collection paths, themes)
    ├── firebase.js       # Dedicated Firestore service: queries, normalization & error handling
    ├── storage.js        # LocalStorage service for solved IDs, bookmarks & preferences
    ├── charts.js         # Chart.js lifecycle management (donut & bar charts)
    ├── render.js         # View layer: DOM updates, HTML sanitization, badge rendering
    └── app.js            # Main controller: wires events, debounced search & state sync
```

### 🚀 Deploying the Dashboard to GitHub Pages

#### 1. Set Your Google Cloud Project ID
Open [`docs/js/config.js`](docs/js/config.js) and enter your project ID:
```javascript
export const CONFIG = {
  firebase: {
    projectId: "your-gcp-project-id", // <-- Replace with your Google Cloud project ID
    apiKey: "",                       // Optional
    databaseId: "(default)",
  },
  // ...
};
```

#### 2. Ensure Firestore Rules Allow Public Read Access
In your Google Cloud Console or Firebase Console, ensure your Firestore Security Rules grant read-only access to `sent_problems` and `state/progress` (write operations remain strictly blocked to public users and reserved for your Cloud Run IAM service account):

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /sent_problems/{document} {
      allow read: if true;
      allow write: if false;
    }
    match /state/progress {
      allow read: if true;
      allow write: if false;
    }
  }
}
```

#### 3. Enable GitHub Pages
1. Push your repository to GitHub (`git add docs/ && git commit -m "feat: dashboard" && git push`).
2. In your GitHub repository, navigate to **Settings** → **Pages**.
3. Under **Build and deployment**:
   - **Source**: `Deploy from a branch`
   - **Branch**: `main`
   - **Folder**: `/docs`
4. Click **Save**. Your dashboard will be live at:
   `https://<your-username>.github.io/<repo-name>/`

---

## 🚀 Setup & Installation

### Prerequisites
- Python 3.10+
- Gmail account with an App Password
- Google Gemini API key (free tier available)
- GitHub account (for GitHub Actions) or Google Cloud project (for Cloud Run + Firestore)

---

### Step 1: Get a Gemini API Key
1. Go to [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Click **Create API key**.
3. Select or create a Google Cloud project.
4. Copy the generated key.

---

### Step 2: Set up Gmail App Password
1. Go to [https://myaccount.google.com/security](https://myaccount.google.com/security).
2. Enable **2-Step Verification** if not already enabled.
3. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
4. Enter an app name (e.g., `DSA Emailer`) and click **Create**.
5. Copy the generated 16-character password (remove any spaces).

---

### Step 3: Clone & Configure

```bash
git clone <your-repo-url>
cd DSA-Problems-Emailer
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` in your text editor and fill in your credentials:

```ini
GEMINI_API_KEY=AIzaSy...
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-gmail@gmail.com
SENDER_PASSWORD=your-16-char-app-password
RECIPIENT_EMAIL=your-personal-email@example.com
```

---

### Step 4: Test Locally

Run the following CLI commands to verify your setup:

```bash
# 1. Test your SMTP credentials and receive a test email
python -m src.main test-email

# 2. Fetch and deduplicate problems from all sources to build the cache
python -m src.main refresh

# 3. View current progress, difficulty breakdown, and streak stats
python -m src.main stats

# 4. Trigger today's daily 4-problem email
python -m src.main daily
```

---

### Step 5: Automation Options

#### Option A: Serverless Google Cloud Run (Recommended for Cloud Setup)
Deploy the service using the automated deployment scripts:
- **Windows (PowerShell)**: `.\deploy.ps1`
- **Linux / macOS**: `./deploy.sh`

This script sets up:
1. Google Cloud Firestore database.
2. Google Cloud Secret Manager for credentials.
3. Google Cloud Run service with authenticated invoker accounts.
4. Google Cloud Scheduler jobs for daily delivery (8:00 AM IST) and weekly reports (Sunday 9:00 AM IST).

#### Option B: GitHub Actions Cron
If you prefer running via GitHub Actions:
1. Push your repository to GitHub:
   ```bash
   git add .
   git commit -m "Initial setup"
   git push origin main
   ```
2. Navigate to **Settings** → **Secrets and variables** → **Actions**.
3. Add secrets: `GEMINI_API_KEY`, `SENDER_EMAIL`, `SENDER_PASSWORD`, `RECIPIENT_EMAIL`.
4. Under **Settings** → **Actions** → **General** → **Workflow permissions**, select **Read and write permissions**.

---

## 📧 Email Formats

### 1. Daily Practice Email (Mystery Format)
- **Subject**: `🧩 Daily DSA Practice — Month Day, Year`
- **Visual Style**: Clean dark navy theme (`#1a1a2e`), card panels (`#16213e`), and crimson accents (`#e94560`).
- **Mystery Content**: Each problem card lists **only** the problem name and a "Solve Problem &rarr;" button.
- **Hidden Metadata**: Difficulty levels, topic classifications, and source platforms are **intentionally omitted** so you approach each problem without bias.
- **Footer**: Tracks lifetime consistency (`Day X • Y/Z A2Z problems completed`), a motivational prompt, and an **interactive button linking directly to your live Progress Dashboard**.

### 2. Weekly Progress Report
- **Subject**: `📊 Weekly DSA Progress — Week N`
- **Schedule**: Sent every Sunday or triggered via `python -m src.main weekly`.
- **Summary Metrics**: Highlighting problems sent this week, current daily streak (🔥), and total problems solved.
- **Topics Covered**: Comprehensive list of all algorithmic topics practiced throughout the week.
- **Visual Difficulty Distribution**: Colored progress bars for Easy (Green), Medium (Amber), and Hard (Crimson) problems.
- **A2Z Sheet Progress**: Percentage bar displaying completion of Striver's A2Z DSA sheet.
- **AI Coaching Insights**: Gemini generates personalized feedback, highlighting consistency, strengths, and recommended focus areas for the upcoming week.
- **Dashboard Shortcut**: Direct button to open your live GitHub Pages dashboard to review question history, track solved status, and revisit bookmarked problems.

---

## 🔧 CLI Commands

| Command | Arguments | Description |
|---|---|---|
| `python -m src.main daily` | — | Runs the daily routine: selects 4 problems, sends the mystery email, and logs state. |
| `python -m src.main weekly` | — | Compiles weekly statistics, generates AI coaching insights, and sends the weekly report. |
| `python -m src.main refresh` | — | Fetches problems from all 4 sources, deduplicates them, and updates `data/problem_cache.json`. |
| `python -m src.main stats` | — | Displays current streak, total problems sent, difficulty distribution, and A2Z sheet progress in terminal. |
| `python -m src.main test-email` | `--to <email>` *(optional)* | Sends a verification email to test SMTP connectivity and credentials. |

---

## 📁 Project Structure

```
DSA-Problems-Emailer/
├── .github/
│   └── workflows/
│       ├── daily_email.yml      # Daily delivery cron workflow (8:00 AM IST)
│       └── weekly_report.yml    # Weekly summary report workflow (Sunday 6:00 PM IST)
├── data/
│   ├── a2z_fallback.json        # Curated offline dataset for Striver's A2Z Sheet
│   ├── gfg_problems.json        # Curated offline dataset for GeeksforGeeks problems
│   ├── problem_cache.json       # Master deduplicated problem pool across all sources
│   ├── progress.json            # Cumulative statistics, streak counter, topic metrics
│   └── sent_log.json            # Complete history of every problem ever dispatched
├── docs/                        # 🌐 GitHub Pages Live Dashboard
│   ├── index.html               # Single-page dashboard UI (Tailwind + Lucide + Chart.js)
│   ├── data/                    # Local JSON fallback data
│   │   ├── progress.json
│   │   └── sent_log.json
│   └── js/
│       ├── config.js            # GCP Project ID, Firestore paths, themes
│       ├── firebase.js          # Firestore client service
│       ├── storage.js           # LocalStorage solver & bookmark state manager
│       ├── charts.js            # Chart.js visualization service
│       ├── render.js            # DOM presentation and badge rendering service
│       └── app.js               # Application coordinator & event dispatcher
├── src/
│   ├── fetchers/
│   │   ├── __init__.py          # Exports problem fetcher routines
│   │   ├── a2z_fetcher.py       # Scrapes takeuforward.org with JSON & HTML fallbacks
│   │   ├── codeforces_fetcher.py# Queries official Codeforces REST API
│   │   ├── gfg_fetcher.py       # Loads local GFG dataset with web scraper fallback
│   │   └── leetcode_fetcher.py  # Paginates LeetCode public GraphQL API
│   ├── __init__.py
│   ├── agent.py                 # Gemini AI orchestrator with native function calling
│   ├── cloud_state.py           # Google Cloud Firestore persistent state manager
│   ├── email_builder.py         # Responsive dark-theme HTML email generator
│   ├── mailer.py                # SMTP client with STARTTLS and plain-text fallback
│   ├── main.py                  # CLI entry point and argument parsing
│   ├── selector.py              # Difficulty quota and topic diversity selector
│   └── state.py                 # Automatic state manager (Firestore or local JSON)
├── app.py                       # FastAPI Cloud Run entry point for scheduled HTTP triggers
├── deploy.ps1                   # Automated GCP deployment script (PowerShell)
├── deploy.sh                    # Automated GCP deployment script (Bash)
├── Dockerfile                   # Container definition for Google Cloud Run
├── config.py                    # Global constants, paths, quotas, and topic mappings
├── README.md                    # Project documentation
└── requirements.txt             # Python package dependencies
```

---

## 🤖 How the AI Agent Works

The system utilizes Google's `google-genai` SDK with **Gemini Function Calling** (`gemini-2.5-flash`) to autonomously orchestrate problem curation.

```
       ┌────────────────────────────────────────────────────────┐
       │                   Gemini 2.5 Flash                     │
       └──────────────────────────┬─────────────────────────────┘
                                  │
                  Function Calls  │  Tool Outputs
                                  ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │ • tool_fetch_problems()        ──> Checks and refreshes problem cache   │
 │ • tool_get_selection_stats()   ──> Analyzes unsent & difficulty pools   │
 │ • tool_select_daily_problems() ──> Backtracking DFS quota & topic check │
 │ • tool_send_daily_email()      ──> Assembles and dispatches HTML email  │
 │ • tool_log_sent()              ──> Atomically updates state and streaks │
 │ • tool_generate_weekly_report()──> Synthesizes weekly report & insights │
 └─────────────────────────────────────────────────────────────────────────┘
```

1. **System Prompt**: Directs the agent to evaluate problem availability, select the 4 problems according to strict diversity constraints, dispatch the email, and record state.
2. **Autonomous Tool Loop**: Gemini calls tool functions sequentially, inspects the JSON responses, and decides the next action.
3. **Zero-Failure Fallback**: If `GEMINI_API_KEY` is missing, quota is exhausted, or the network fails, the system automatically runs `run_daily_fallback()` / `run_weekly_fallback()`. The rule-based Python fallback executes the exact same selection algorithm and sends the email without skipping a beat.

---

## 🛠️ Troubleshooting

### 1. `SMTPAuthenticationError` (535 5.7.8 Username and Password not accepted)
- **Cause**: Incorrect email or password. Gmail blocks regular account passwords.
- **Fix**: Ensure you generated a **16-character App Password** via [Google App Passwords](https://myaccount.google.com/apppasswords) with 2-Step Verification enabled. Remove all spaces from the password string.

### 2. GitHub Actions Fails on `git push`
- **Error**: `remote: Permission to <user>/<repo> denied to github-actions[bot]`.
- **Fix**: In your GitHub repo, navigate to **Settings** → **Actions** → **General** → **Workflow permissions**, select **Read and write permissions**, and save.

### 3. Gemini API Quota or Connection Errors
- **Behavior**: The application logs a warning and automatically switches to `run_daily_fallback()`.
- **Verification**: Check your Gemini API key and quota in [Google AI Studio](https://aistudio.google.com/). Ensure `GEMINI_API_KEY` is correctly set in `.env` or repository secrets.

### 4. Dashboard Displays "Using Local Data"
- **Cause**: The Google Cloud Project ID in [`docs/js/config.js`](docs/js/config.js) is either unset or the Firestore security rules deny public reads.
- **Fix**: Update `projectId` in `docs/js/config.js` and verify that Firestore security rules contain `allow read: if true;` for `sent_problems` and `state/progress`.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
