# McAfee Competitor Pricing Agent 🛡️

An agentic Streamlit app that uses Claude + live web search to compare
competitor pricing against McAfee products in real time.

## Quick Start

### 1. Clone / download this folder

### 2. Create a virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add your API key
```bash
cp .env.example .env
# Edit .env and paste your Anthropic API key
```
Or just enter it directly in the app's sidebar.

Get your key at: https://console.anthropic.com

### 5. Run the app
```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Features
- 🔍 Live web search via Claude's web_search tool
- 🛡️ Pre-loaded McAfee product list + custom product input
- 📊 Price bar chart comparison
- 💰 Best deal auto-highlighted
- ⬇️ Export results as JSON
