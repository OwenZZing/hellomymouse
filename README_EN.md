# 🔭 Hypothesis Maker — User Guide (English)

> Lab paper PDFs → AI analysis → Research Starter Kit (.docx), automated  
> Made by @hellomymouse · kby930@gmail.com

---

## What is this?

A tool for new graduate students (or undergraduate interns) joining a research lab.  
Drop your lab's PDF papers into a folder, and the AI automatically produces a Word document containing:

- Lab project list and overview
- "What is research?" intro section (written for undergrad-level readers)
- Lab techniques and equipment with plain-language explanations
- Per-paper summaries (key findings + limitations)
- 7 research hypothesis candidates (H1–H6: safe/incremental, H7: trendy)
  - Each includes: impact stars, estimated timeline, evaluation metrics, baseline, and fallback plan
- Cost estimates (KRW, Korean market)
- PI confirmation checklist
- Background Knowledge Guide (core concepts / keywords / recommended journals)
- First 3-month roadmap

---

## ⚠ Always Check with Your Seniors Before Running Experiments

The AI analyzes only what is written in the papers. **There is often a large gap between what's published and current lab reality.**  
Before pursuing any hypothesis, confirm the following with a senior student or your advisor:

| Check | Why It Matters |
|-------|----------------|
| **Is the robot / equipment / sensor from the paper still in the lab?** | Hardware gets upgraded, replaced, or breaks down over time |
| **Can I actually use it?** | Parts may have been moved to another robot or project |
| **Is the experiment environment ready? (GPU servers, simulator licenses, etc.)** | Infrastructure changes |
| **Does this hypothesis align with the lab's current direction?** | AI-generated hypotheses are candidates, not guarantees |

> If hardware access is uncertain, refer to the **Fallback Plan** in each hypothesis for simulation alternatives (Isaac Gym, Gazebo, MuJoCo, etc.).

---

## No API Credits? — Manual Generation via Claude Code

If your API credits run out or you've hit your daily limit,  
you can generate the same report format by **pasting paper abstracts directly into Claude Code**.

### How it works

1. Copy the abstracts from your lab's papers  
2. Ask Claude Code something like:

```
Assigned project: [project name]
Please generate a Research Starter Kit report based on the abstracts below.
Papers folder: [folder path]

[paste abstracts here]
```

3. Claude writes a one-off report-generator script for you (save it inside a dedicated folder, e.g. `scratch/`, **not** at the repo root)
4. Run the script to produce the `.docx`:

```bash
python scratch/your_report_script.py
```

> Deprecated root-level scripts like `generate_report_*.py` have been moved to `../legacy_archive/`. Do not run them — they drift from the current app and are no longer maintained.

### Comparison

| | Program (API) | Claude Code manual |
|---|---|---|
| Full paper analysis | ✅ Full PDF parsing | ⚠ Abstract-level |
| Speed | 3–10 min, automated | Instant after Claude responds |
| Cost | API credits | None (Claude Code subscription) |
| Output format | Same (.docx) | Same (.docx) |

> Output files land under `Output/` as `Research_Starter_Kit_<name>.docx`.

---

## Installation

### Option A: Executable (recommended, no Python needed)

Double-click `HypothesisMaker.exe`. No installation required.

### Option B: Run from source (developers)

```bash
# Requires Python 3.11+
cd Hypothesis-Finder
python -m venv venv
source venv/Scripts/activate        # Windows
pip install -r requirements.txt
python main.py
```

---

## How to Use

### Step 1 — Gather Papers
Collect as many recent (last 5 years) PDF papers from your lab as possible into a single folder.  
**10–20 papers** is ideal. Fewer papers reduce analysis quality.

### Step 2 — Enter Your API Key
Select an AI provider and enter your API key.

| AI | Get API Key | Cost (per 10 papers) |
|----|------------|----------------------|
| **Claude (high quality)** | [console.anthropic.com](https://console.anthropic.com) → API Keys | ~$0.30–0.80 |
| **OpenAI GPT-4o** | [platform.openai.com](https://platform.openai.com) → API keys | ~$0.50–1.50 |
| **Gemini Flash (cheap / free)** | [aistudio.google.com](https://aistudio.google.com) → Get API key | ~$0.05–0.20 |

> 💡 **On a tight budget? Use Gemini Flash.**  
> Google AI Studio offers free API keys with generous limits.

> API keys are saved locally at `~/.hypothesis_maker_config.json`.  
> Delete after use on shared computers.

### Step 3 — Select Lab Papers Folder
Click **Browse** next to "Lab Papers Folder" and select the folder containing your PDFs.

### Step 4 — (Optional) Add Reference Papers
If your professor recommended papers outside the lab's own publications, put them in a separate folder and select it under "Additional Reference Papers Folder."

### Step 5 — Detect Lab Projects (Stage 0)
Click **"🔍 Detect Project List"**.  
The AI reads only titles and abstracts to identify lab projects. (30 sec–1 min)

### Step 6 — Select Your Assigned Project
- If your professor assigned you a specific project, select it from the list or type it directly.
- Leave blank to analyze all projects equally.

### Step 7 — (Optional) Professor's Instructions
Enter any additional guidance your professor has given: preferred methods, specific papers to reference, target direction, etc.

### Step 8 — Run Full Analysis
Click **"▶ Start Analysis"**.  
Takes 3–10 minutes depending on the number of papers. Progress is shown in the log area.

### Step 9 — Save and Open
When analysis completes, choose a save location and click **"📄 Generate Report"**.  
Open the `.docx` file in Microsoft Word.

---

## Impact Star Rating Guide

| Stars | Meaning |
|-------|---------|
| ★☆☆☆☆ | Barely passable thesis. Expect heavy committee criticism |
| ★★☆☆☆ | Solid enough to graduate. Job market needs other credentials |
| ★★★☆☆ | Strong thesis. Explainable to employers as a key credential |
| ★★★★☆ | Takes longer, but you'll have your pick of positions when done |
| ★★★★★ | Field-changing paper. Worth it even if it takes 5+ years |

> ※ Time estimates assume you already know the techniques involved.  
> Add **2–3×** for learning curve when working with new methods.

---

## Disclaimer

- This tool produces **AI-generated drafts**. Content may be inaccurate or incomplete.
- Hypothesis ratings and timelines are AI estimates. Always **verify with your advisor and senior lab members**.
- Clearly state this is an AI-generated draft if you share it with your professor.
- Keep your API key secure and do not share it.

---

## Building the exe (developers)

```bash
pip install pyinstaller
pyinstaller build.spec
```

The finished executable will be at `dist/HypothesisMaker.exe`.

---

## Project Structure

```
Hypothesis-Finder/
├── main.py                  # Entry point
├── config.py                # Config load/save
├── requirements.txt
├── gui/
│   ├── app.py               # Main window
│   └── widgets.py           # Custom widgets
├── parser/
│   ├── pdf_reader.py        # PDF text extraction (PyMuPDF)
│   └── section_splitter.py  # Section detection
├── analyzer/
│   ├── api_client.py        # Claude / OpenAI / Gemini client
│   ├── prompts.py           # Stage 0 / 1 / 2 prompts
│   └── processor.py         # Analysis pipeline
├── report/
│   ├── docx_builder.py      # JSON → Word document
│   └── templates.py         # Style constants
├── build.spec               # PyInstaller build config
├── README_KO.md             # Korean user guide
└── README_EN.md             # This file
```

---

## User Reviews

> "연구실에서 나간 논문들을 한눈에 볼 수 있고 어떤 실험을 하는 곳인지 이해하는데 도움이 될 것 같아요"
> — @김진영

---

## Contact

- Threads: **@hellomymouse**
- Email: **kby930@gmail.com**
