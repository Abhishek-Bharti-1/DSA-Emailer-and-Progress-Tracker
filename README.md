# 🧩 DSA Problems Daily Emailer

An automated, AI-curated system that emails 4 Data Structures & Algorithms (DSA) problems to your inbox every single morning. Sourced primarily from **Striver's A2Z DSA Sheet** and supplemented by **LeetCode**, **Codeforces**, and **GeeksforGeeks**, it ensures disciplined, structured practice with zero spoilers and guaranteed non-repetition.

---

## ✨ Features

- **4 Problems Daily**: Balanced quota of **1 Easy, 2 Medium, 1 Hard** problem delivered every day.
- **Strict Topic Diversity**: All 4 problems are guaranteed to come from different topics (e.g., Arrays, Dynamic Programming, Trees, Binary Search).
- **Mystery Format (Zero Spoilers)**: Daily emails deliberately hide difficulty, topic tags, and platform names. You solve each problem purely on merit, mirroring real interview environments.
- **A2Z Sheet Priority**: Focuses on Striver's comprehensive A2Z DSA course (~455 problems). Automatically supplements from fallback sources (LeetCode, GFG, Codeforces) when needed.
- **Weekly Progress Reports**: Automated Sunday progress digest summarizing problems solved, difficulty distributions with visual progress bars, streak metrics, and personalized coaching insights powered by Gemini.
- **Gemini AI Agent**: Driven by Google's `gemini-2.0-flash` with native Function Calling (`google-genai` SDK) to orchestrate curation, delivery, and logging — backed by an automatic, zero-dependency Python fallback if the API is ever unreachable.
- **No Repeated Problems Ever**: Persistent state management tracks every problem ever sent across all platforms via canonical URL slugs and normalized titles.

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
┌───────────────────────┐         ┌─────────────────────────────┐
│  GitHub Actions / CLI │ ──────> │   Gemini AI Agent / Router  │
│  (Cron: 8:00 AM IST)  │         │   (Function Calling Loop)   │
└───────────────────────┘         └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │   Intelligent Selector      │
                                  │   (1E, 2M, 1H + 4 Topics)   │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │ Responsive HTML Mailer      │
                                  │ (STARTTLS via Gmail SMTP)   │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  State Updates & Commits    │
                                  │  • sent_log.json            │
                                  │  • progress.json            │
                                  └─────────────────────────────┘
```

### Problem Flow
1. **Fetch & Cache**: Fetchers extract problems from all 4 sources and normalize them into a unified schema across 19 standard topics.
2. **Deduplicate**: Cross-platform duplicates are eliminated by matching URL slugs and normalized titles, retaining the highest-priority source version (`a2z_sheet` > `leetcode` > `gfg` > `codeforces`).
3. **Select**: The selector filters out previously sent problem IDs, prioritizes A2Z Sheet candidates, and runs depth-first backtracking to pick 1 Easy, 2 Medium, and 1 Hard problem from 4 distinct topics.
4. **Dispatch**: The email builder renders a mobile-responsive dark navy template and sends it via Gmail SMTP with a plain-text fallback.
5. **Persist**: The sent problems are atomically logged, streaks and progress metrics are recalculated, and state files are committed back to the repository.

---

## 🚀 Setup

### Prerequisites
- Python 3.10+
- Gmail account with an App Password
- Google Gemini API key (free tier available)
- GitHub account (for automated scheduling with GitHub Actions)

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

### Step 5: Deploy to GitHub Actions

Automate daily delivery using the built-in GitHub Actions workflow:

1. Push your repository to GitHub:
   ```bash
   git add .
   git commit -m "Initial setup"
   git push origin main
   ```
2. Navigate to your repository on GitHub: **Settings** → **Secrets and variables** → **Actions**.
3. Click **New repository secret** and add each secret:
   - `GEMINI_API_KEY`
   - `SENDER_EMAIL`
   - `SENDER_PASSWORD`
   - `RECIPIENT_EMAIL`
4. Go to **Settings** → **Actions** → **General** → **Workflow permissions**, select **Read and write permissions**, and click **Save** (required for the workflow to commit updated state files).
5. Switch to the **Actions** tab, select **Daily DSA Email**, and click **Run workflow** to test manual triggering.

---

## 📧 Email Formats

### 1. Daily Practice Email (Mystery Format)
- **Subject**: `🧩 Daily DSA Practice — Month Day, Year`
- **Visual Style**: Clean dark navy theme (`#1a1a2e`), card panels (`#16213e`), and crimson accents (`#e94560`).
- **Mystery Content**: Each problem card lists **only** the problem name and a "Solve Problem &rarr;" button.
- **Hidden Metadata**: Difficulty levels, topic classifications, and source platforms are **intentionally omitted** so you approach each problem without bias.
- **Footer**: Tracks lifetime consistency: `Day X • Y/Z A2Z problems completed` followed by `Happy Coding! 🚀`.

### 2. Weekly Progress Report
- **Subject**: `📊 Weekly DSA Progress — Week N`
- **Schedule**: Sent every Sunday or triggered via `python -m src.main weekly`.
- **Summary Metrics**: Highlighting problems sent this week, current daily streak (🔥), and total problems solved.
- **Topics Covered**: Comprehensive list of all algorithmic topics practiced throughout the week.
- **Visual Difficulty Distribution**: Colored progress bars for Easy (Green), Medium (Amber), and Hard (Crimson) problems.
- **A2Z Sheet Progress**: Percentage bar displaying completion of Striver's A2Z DSA sheet.
- **AI Coaching Insights**: Gemini generates personalized feedback, highlighting consistency, strengths, and recommended focus areas for the upcoming week.

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
│       └── daily_email.yml      # GitHub Actions cron schedule (8:00 AM IST daily)
├── data/
│   ├── a2z_fallback.json        # Curated offline dataset for Striver's A2Z Sheet
│   ├── gfg_problems.json        # Curated offline dataset for GeeksforGeeks problems
│   ├── problem_cache.json       # Master deduplicated problem pool across all sources
│   ├── progress.json            # Cumulative statistics, streak counter, topic metrics
│   └── sent_log.json            # Complete history of every problem ever dispatched
├── src/
│   ├── fetchers/
│   │   ├── __init__.py          # Exports problem fetcher routines
│   │   ├── a2z_fetcher.py       # Scrapes takeuforward.org with JSON & HTML fallbacks
│   │   ├── codeforces_fetcher.py# Queries official Codeforces REST API
│   │   ├── gfg_fetcher.py       # Loads local GFG dataset with web scraper fallback
│   │   └── leetcode_fetcher.py  # Paginates LeetCode public GraphQL API
│   ├── __init__.py
│   ├── agent.py                 # Gemini AI orchestrator with native function calling
│   ├── email_builder.py         # Responsive dark-theme HTML email generator
│   ├── mailer.py                # SMTP client with STARTTLS and plain-text fallback
│   ├── main.py                  # CLI entry point and argument parsing
│   ├── selector.py              # Difficulty quota and topic diversity selector
│   └── state.py                 # Thread-safe atomic JSON state manager
├── .env.example                 # Template for environment configuration
├── .gitignore                   # Ignores .env and virtual environments (tracks data/)
├── config.py                    # Global constants, paths, quotas, and topic mappings
├── README.md                    # Project documentation
└── requirements.txt             # Python package dependencies
```

---

## 🔄 Adding Problems Manually

You can add or curate custom problems by editing the local fallback files in `data/`.

### Editing `data/gfg_problems.json` and `data/a2z_fallback.json`
Entries must follow the unified JSON problem schema:

```json
[
  {
    "id": "gfg-0101",
    "title": "Subarray with Given Sum",
    "topic": "Arrays",
    "difficulty": "Medium",
    "source": "gfg",
    "url": "https://www.geeksforgeeks.org/problems/subarray-with-given-sum-1587115621/1",
    "platform": "gfg"
  },
  {
    "id": "a2z-0500",
    "title": "Alien Dictionary",
    "topic": "Graphs",
    "difficulty": "Hard",
    "source": "a2z_sheet",
    "url": "https://leetcode.com/problems/alien-dictionary/",
    "platform": "leetcode"
  }
]
```

### Guidelines for Manual Entries:
1. **Topic Normalization**: Use one of the 19 standard topics:
   *Arrays, Strings, Linked Lists, Stacks & Queues, Trees, Binary Search Trees, Binary Search, Graphs, Dynamic Programming, Greedy, Backtracking, Bit Manipulation, Math, Heaps, Tries, Sliding Window, Two Pointers, Recursion, Sorting*.
2. **Difficulty**: Must be `Easy`, `Medium`, or `Hard` (GFG `School` and `Basic` levels automatically map to `Easy`).
3. **Unique IDs**: Use prefix conventions like `gfg-NNNN` or `a2z-NNNN`.
4. **Re-caching**: After modifying either file, run `python -m src.main refresh` to re-index the cache.

---

## ⚙️ Configuration

Environment variables can be defined in `.env` (for local runs) or GitHub Repository Secrets (for automated runs):

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(Required for AI)* | Google Gemini API key used by the curator agent and weekly insights. |
| `SMTP_SERVER` | `smtp.gmail.com` | Hostname of your outgoing mail server. |
| `SMTP_PORT` | `587` | Port for SMTP communication with STARTTLS encryption. |
| `SENDER_EMAIL` | *(Required)* | Gmail address used to transmit the practice emails. |
| `SENDER_PASSWORD` | *(Required)* | 16-character Google App Password (not your Google account password). |
| `RECIPIENT_EMAIL` | *(Required)* | Email address where daily practice and reports will be delivered. |

### Configurable Constants (`config.py`)
- `DAILY_EASY = 1`, `DAILY_MEDIUM = 2`, `DAILY_HARD = 1`: Customizes the daily difficulty quota.
- `SOURCE_PRIORITY = ["a2z_sheet", "leetcode", "gfg", "codeforces"]`: Order of priority when selecting problems.
- `GEMINI_MODEL = "gemini-2.0-flash"`: Fast, high-performance Gemini model used for agent orchestration and insights.

---

## 🤖 How the AI Agent Works

The system utilizes Google's `google-genai` SDK with **Gemini Function Calling** to autonomously orchestrate problem curation.

```
       ┌────────────────────────────────────────────────────────┐
       │                   Gemini 2.0 Flash                     │
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

## 📊 State Files

All state files reside in the `data/` directory and are managed by `StateManager` using thread-safe, atomic disk writes (`tempfile` + `os.replace`):

- **`data/sent_log.json`**:
  An append-only log of every problem sent. Each record contains:
  ```json
  {
    "id": "a2z-0012",
    "title": "Next Permutation",
    "topic": "Arrays",
    "difficulty": "Medium",
    "source": "a2z_sheet",
    "date": "2026-11-21"
  }
  ```
- **`data/problem_cache.json`**:
  Stores all available, deduplicated problems from all 4 sources.
- **`data/progress.json`**:
  Maintains aggregated stats updated after each dispatch:
  ```json
  {
    "total_sent": 28,
    "by_source": { "a2z_sheet": 24, "leetcode": 4 },
    "by_topic": { "Arrays": 7, "Trees": 7, "Graphs": 7, "Dynamic Programming": 7 },
    "by_difficulty": { "Easy": 7, "Medium": 14, "Hard": 7 },
    "streak_days": 7,
    "a2z_total": 455,
    "a2z_sent": 24,
    "dates": ["2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21"]
  }
  ```

> [!NOTE]
> `data/sent_log.json` and `data/progress.json` are intentionally tracked in Git so that GitHub Actions can persist and commit state across daily runs.

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

### 4. Problem Cache is Empty
- **Symptom**: `Failed to select daily problems from pool.`
- **Fix**: Run `python -m src.main refresh` to re-fetch problems from online sources, or verify that `data/a2z_fallback.json` exists.

### 5. Email Arriving in Spam / Junk Folder
- **Fix**: Open the email in your email client, click **Report not spam** or add your sender address to your contacts / VIP list.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
