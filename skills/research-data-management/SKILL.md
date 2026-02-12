---
name: research-data-management
description: Follow best practices for research data management, including folder structure, file naming, and documentation standards
---

# Research Data Management Skill

This skill guides AI agents to help users organize research projects following established data management best practices, making projects suitable for long-term preservation and repository publication.

## Core Principles

When working with research projects, proactively identify and address data management issues:
- Maintain clear separation between raw data, processed data, and code
- Preserve original data files in immutable form
- Follow consistent file naming conventions
- Ensure adequate documentation and licensing
- Document AI/agent usage for transparency and reproducibility

## Standard Folder Structure

Research projects should follow this directory structure:

### Required Directories

```
project-root/
├── data/
│   ├── raw/          # Original, immutable source data
│   └── processed/    # OR interim/ OR active/ (ask user preference)
├── code/             # OR src/ (all scripts and source code)
├── README.md         # Project documentation
├── LICENSE           # License file
└── CITATION.cff      # Citation metadata (recommended for research)
```

### What Should Go Where

- **`data/raw/`**: Original data files exactly as received/collected. Never modify these files.
- **`data/processed/` (or similar)**: Cleaned, transformed, or analyzed data outputs
- **`code/` or `src/`**: All scripts, notebooks, and source code
- **Root directory**: README.md, LICENSE, CITATION.cff, and dependency files only

## Agent Actions

### 1. Data Files in Wrong Location

**When you detect**: Data files (csv, xlsx, json, parquet, etc.) outside of `data/` directory

**Action**: 
- Inform the user which files should be moved
- Suggest moving to `data/raw/` if original source data, or `data/processed/` if generated output
- Ask for confirmation before moving files
- Update any file path references in code accordingly

### 2. Missing README.md

**When you detect**: No README.md in project root

**Action**:
- Prompt user to create one
- Offer template options:
  - Basic: Project title, description, installation, usage
  - Research: Above + data sources, methodology, citation
  - Detailed: Above + folder structure documentation, file naming conventions

### 3. Missing LICENSE

**When you detect**: No LICENSE file in project root

**Action**:
- Explain importance for open sharing and reuse
- Suggest appropriate licenses based on project type:
  - **Code projects**: MIT, Apache 2.0, GPL-3.0
  - **Data/documentation**: CC BY 4.0, CC0
  - **Mixed**: Dual license (e.g., code under MIT, data under CC BY 4.0)
- Offer to create the license file with user's choice

### 4. Missing CITATION.cff

**When you detect**: Research project without CITATION.cff file

**Action**:
- Recommend creating CITATION.cff for proper citation of research software/data
- Offer to create the file with standard metadata:
  - `cff-version`: 1.2.0
  - `title`: Project title
  - `authors`: Author names with ORCID if available
  - `version`: Current version
  - `date-released`: Release/publication date
  - `url` or `repository-code`: Project URL
  - `license`: License identifier
  - `keywords`: Relevant keywords
  - `abstract`: Brief project description
- For research output: include `preferred-citation` for associated paper
- Note: This makes the project easily citable and compatible with GitHub, Zenodo, and other repositories

### 5. Mixed Data and Code

**When you detect**: Code files in data folders or data files in code folders

**Action**:
- List the specific files that are misplaced
- Suggest a reorganization plan with specific file moves
- Update import statements, file paths, and references in code
- Ask for confirmation before making changes

### 6. Missing Dependencies File

**When you detect**: Project lacks a dependencies/environment file

**Action**: Create appropriate file based on detected language:

- **Python**: 
  - `requirements.txt` (simple projects)
  - `pyproject.toml` (modern Python projects)
  - `pixi.toml` (if conda dependencies detected)
  
- **R**: 
  - `renv.lock` (recommend initializing renv)
  - `DESCRIPTION` file for R packages
  
- **JavaScript/Node**: 
  - `package.json`
  
- **Julia**:
  - `Project.toml`

If dependencies already exist in the code (import/library statements), extract and populate the dependencies file.

### 7. Document AI/Agent Usage

**When you detect**: You (the agent) are actively assisting with a research project

**Action**: Proactively document your involvement for transparency:

**Where to document**:
- Create or update an `AI_USAGE.md` file in the project root, OR
- Add an "AI Assistance" section to README.md if documentation is minimal

**Required information**:
- **Model name and version**: (e.g., "GPT-4", "Claude 3.5 Sonnet", "GitHub Copilot with GPT-4")
- **Date(s) of use**: When the AI assistance occurred
- **Tasks/capacity**: Specific ways AI was used:
  - Code generation (specify which files/functions)
  - Debugging and error resolution
  - Data analysis and visualization
  - Documentation writing
  - Project structure and organization
  - Literature review or research assistance
  - Code review and optimization
- **Extent of use**: Approximate percentage or description (e.g., "AI-generated initial implementation, human-reviewed and modified")
- **Human oversight**: Clarify that work was reviewed/validated by humans

**Template for AI_USAGE.md**:
```markdown
# AI Usage Documentation

This project used AI assistance as documented below for transparency and reproducibility.

## AI Model Information
- Model: [name and version]
- Provider: [e.g., OpenAI, Anthropic, GitHub]
- Access date(s): [date range]

## Usage Details

### Code Development
- [Specific files or functions where AI generated/assisted with code]
- [Description of AI role vs. human modifications]

### Data Analysis
- [Any AI-assisted analysis, interpretation, or visualization]

### Documentation
- [Which documentation was AI-assisted]

### Other Tasks
- [Any other relevant AI contributions]

## Human Oversight
[Describe review process, validation methods, and human decision-making]

## Limitations and Considerations
[Any known limitations, potential biases, or areas requiring extra scrutiny]
```

**Best practices**:
- Document AI use even for small contributions
- Be specific about what AI did vs. what humans decided/validated
- Update throughout the project lifecycle
- For publications, follow journal-specific AI disclosure requirements
- Consider adding to CITATION.cff under `tools` if the AI significantly contributed

## File Naming Conventions

### Detection
Check if README.md documents a file naming convention. If not, check for existing patterns in the project.

### Recommendation
If no convention exists, suggest one of these formats:

1. **Date-based**: `YYYY-MM-DD_descriptive-name_version.ext`
   - Example: `2026-02-11_survey-responses_v01.csv`

2. **Project-based**: `projectname_datatype_YYYYMMDD.ext`
   - Example: `climate_temperature_20260211.csv`

3. **Sequential**: `projectname_descriptive-name_001.ext`
   - Example: `watershed_water-quality_001.xlsx`

**Action**:
- Ask user's preference
- Document the chosen convention in README.md
- Suggest renaming files that don't follow the convention (with user approval)

## Documentation Standards

### README.md Content
Should include at minimum:
- Project title and brief description
- Data sources and collection methods (for research)
- Installation/setup instructions
- Usage examples or key commands
- File/folder structure explanation
- File naming conventions
- Citation information (reference CITATION.cff if it exists)
- AI assistance disclosure (reference AI_USAGE.md if it exists, or include brief note)

### Code Documentation
- Add brief inline comments for complex operations
- Document key parameters and assumptions
- Include docstrings for functions/modules
- No need for separate detailed documentation unless requested

### When to Document in README vs. Separate Files
- **README.md**: Key workflows, common commands, project overview
- **Separate docs**: Only for extensive user guides or API documentation
- Default to README.md for simplicity

## Interaction Guidelines

### Be Proactive but Not Intrusive
- Identify issues when first working with a project
- Suggest fixes, but don't implement without user approval for file moves/renames
- Prioritize critical issues (missing LICENSE, data in wrong locations)

### Ask for Preferences
When multiple valid options exist:
- Processed vs. interim vs. active directory naming
- License type selection
- File naming convention format
- Always document the user's choice in appropriate location

### Preserve User Work
- Never modify files in `data/raw/`
- Always confirm before moving or renaming files
- Update references when reorganizing to prevent breaking code

## Integration with Other Work

When working on data analysis, modeling, or visualization tasks:
1. Check project structure first
2. Suggest improvements if needed
3. Place outputs in appropriate folders
4. Update documentation as you work
5. Ensure reproducibility through proper dependency management

## Examples

### Example 1: Detecting Misplaced Data

```
User's project structure:
project/
├── analysis.py
├── survey_data.csv
└── results.xlsx
```

**Agent response**: "I notice this project has data files in the root directory. For better organization and reproducibility, I recommend creating a `data/` structure. Can I help reorganize this as:
- `survey_data.csv` → `data/raw/survey_data.csv`
- `results.xlsx` → `data/processed/results.xlsx`
- Create a README.md to document the project structure?"

### Example 2: Missing Dependencies

```
User has analysis.py with:
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
```

**Agent response**: "I see your script uses pandas, numpy, and scikit-learn, but there's no requirements.txt. I'll create one to ensure reproducibility:
```
pandas
numpy
scikit-learn
```
Would you like me to include specific versions?"

### Example 3: No Documentation

**Agent response**: "This project doesn't have a README.md yet. I can create one that documents:
- What this analysis does
- The data folder structure
- How to run the main analysis script
- File naming convention (I notice you're using `YYYY-MM-DD_description.csv`)

Would you like a basic, research, or detailed template?"

### Example 4: Creating CITATION.cff

**Agent response**: "I notice this is a research project without a CITATION.cff file. This file makes your work properly citable and is recognized by GitHub, Zenodo, and other platforms. I can create one with:
- Your project title and description
- Author information (including ORCID if you have one)
- License and repository information
- Keywords for discoverability

Would you like me to create this file? If you have a related publication, I can also add a preferred citation reference."

### Example 5: Self-Documenting AI Usage

**Agent action**: After assisting with code generation or analysis:

"I've helped generate the data processing pipeline in `code/process_data.py`. For research transparency, I should document my involvement. I can create an `AI_USAGE.md` file noting:
- Model: [Your model name and version]
- Date: February 11, 2026
- Task: Generated initial data processing code (lines 45-120 in process_data.py)
- Human oversight: Code reviewed and modified by you for domain-specific requirements

This ensures your research is transparent about AI assistance. Would you like me to create this documentation?"

## When NOT to Apply This Skill

- Single-file scripts or experiments not intended for sharing
- Projects with established alternative structures (e.g., Django, Rails have their own conventions)
- When user explicitly states they're following a different standard
- Exploratory/temporary work not meant for preservation

Always respect existing project conventions unless they clearly violate data management best practices or the user asks for help reorganizing.
