# Save to Retainer: Complete iOS / macOS Shortcut Blueprint

This guide walks you through building the **Save to Retainer** Shortcut from scratch in the Apple **Shortcuts** app (building on your Mac with mouse and keyboard is fastest, and it syncs immediately to your iPhone/iPad over iCloud).

---

## 1. Initial Setup & Share Sheet Configuration

1. Open the **Shortcuts** app and click **`+`** (New Shortcut).
2. Name it **`Save to Retainer`** at the top.
3. Choose an icon: click the icon next to the title, pick a color (e.g. Purple/Blue), and select the **Brain** or **Bookmark** glyph.
4. Open the **Shortcut Details Inspector** (the `(i)` button in the right sidebar on Mac, or top right on iPhone):
   - Check **Use as Quick Action** / **Show in Share Sheet**.
   - Under **Share Sheet Types** / **Services Menu**, click **Any** and select **ONLY**:
     - `URLs`
     - `Safari web pages`
   - If there is no input: select **Stop and Respond**.

---

## 2. Global Configuration & Import Questions

### Action 1: Dictionary (The Config Object)
Search for **`Dictionary`** in the action library and add it:
Add the following keys (all type **Text**):
- `AI Provider` ➔ `Google Gemini`
- `API Key` ➔ *(leave empty)*
- `Save Destination` ➔ `Apple Notes`
- `Other URL` ➔ `https://openrouter.ai/api/v1/chat/completions`
- `Other Model` ➔ `meta-llama/llama-3.3-70b-instruct:free`
- `Obsidian Vault Folder` ➔ `Retainer`

### Action 2: Set Variable
Search for **`Set Variable`**:
- Variable Name: `Config`
- Input: `Dictionary` (from Action 1)

---

## 3. Attach Setup Questions (The Onboarding Wizard)

*(This is what pops up when anyone downloads your shared iCloud link!)*

In the right-hand **Inspector** panel (`(i)` icon):
1. Click **Setup Questions** (or **Import Questions**).
2. Click **`+` (Add Question)**:
   - **Action**: Select the `AI Provider` row in Action 1's Dictionary.
   - **Question Text**:
     ```text
     Choose your AI Provider:
     • Google Gemini (Recommended - free API key)
     • ChatGPT
     • Claude
     • Other
     ```
   - **Default Value**: `Google Gemini`
3. Click **`+` (Add Question)**:
   - **Action**: Select the `API Key` row in Action 1's Dictionary.
   - **Question Text**:
     ```text
     Enter your API Key:
     (If using Google Gemini, get your free key in 10 seconds with no credit card at: https://aistudio.google.com)
     (If using 'Other', paste your provider key here).
     ```
   - **Default Value**: *(leave blank)*
4. Click **`+` (Add Question)**:
   - **Action**: Select the `Save Destination` row in Action 1's Dictionary.
   - **Question Text**:
     ```text
     Where should notes be saved?
     • Apple Notes
     • Files
     ```
   - **Default Value**: `Apple Notes`

---

## 4. Define the System Prompt

### Action 3: Text
Search for **`Text`** and paste this exact prompt template:
```text
You are an expert cognitive scientist, technical analyst, and spaced-repetition flashcard author.
Analyze the provided source content and output a clean Markdown note matching this exact structure:

# [Clear, Clickbait-Free Title (<15 words)]

## Abstract
**Quick Summary:** [Concise abstract <100 words]
**Detailed Overview:** [Detailed technical abstract ~250 words explaining mechanisms, context, and outcomes]

## Key Concepts and Takeaways
- [4-8 bulleted technical insights, trade-offs, or mechanisms]

## Detailed Outline
- Chronological or structural walkthrough of the content with key explanations.

## Flashcards
**Q1: [Atomic question testing practical mechanism or key insight]**
- *A:* [Concise 1-2 sentence answer]
**Q2: ...**
```

### Action 4: Set Variable
- Variable Name: `SystemPrompt`
- Input: `Text` (from Action 3)

---

## 5. Content Extraction: YouTube vs. Web Article

### Action 5: If
- Input: `Shortcut Input`
- Condition: **contains**
- Value: `youtu`

---

### [Inside the 'If' Block: YouTube Extraction via InnerTube Android]

#### Action 6: Match Text (Extract Video ID)
- Pattern: `(?<=v=|\/)([0-9A-Za-z_-]{11})`
- In: `Shortcut Input`

#### Action 7: Get Item from List
- Get: **First Item**
- From: `Matches` (from Action 6)
- Rename Output variable to: `VideoID`

#### Action 8: Get Contents of URL (Query InnerTube API)
- URL: `https://www.youtube.com/youtubei/v1/player`
- Method: **`POST`**
- Request Body: **JSON**
  - Add field `videoId` (Text) ➔ `VideoID`
  - Add field `context` (Dictionary):
    - Tap `+` inside `context` and add `client` (Dictionary):
      - Add field `clientName` (Text) ➔ `ANDROID`
      - Add field `clientVersion` (Text) ➔ `20.10.38`

#### Action 9: Get Dictionary Value
- Key: `captions.playerCaptionsTracklistRenderer.captionTracks.1.baseUrl`
- From: `Contents of URL` (from Action 8)

#### Action 10: Get Contents of URL (Download Caption XML)
- URL: Select the Dictionary Value from Action 9
- Method: **`GET`**

#### Action 11: Match Text (Strip XML Tags)
- Pattern: `(?<=<text[^>]*>)([\s\S]*?)(?=<\/text>)|(?<=<p[^>]*>)([\s\S]*?)(?=<\/p>)`
- In: `Contents of URL` (from Action 10)

#### Action 12: Combine Text
- Combine: `Matches` (from Action 11)
- With: **Custom** (Enter a single space: ` `)

#### Action 13: Set Variable
- Variable Name: `ExtractedContent`
- Input: `Combined Text` (from Action 12)

---

### [Inside the 'Otherwise' Block: Web Article Extraction via Jina Reader]

#### Action 14: Get Contents of URL
- URL: `https://r.jina.ai/` + `Shortcut Input`
- Method: **`GET`**
- Headers:
  - `Accept`: `text/plain`

#### Action 15: Set Variable
- Variable Name: `ExtractedContent`
- Input: `Contents of URL` (from Action 14)

*(Right after Action 15 is the **`End If`** block).*

---

## 6. AI Model Routing & API Generation

### Action 16: Get Dictionary Value (Fetch Provider)
- Key: `AI Provider`
- From: `Config`

### Action 17: Get Dictionary Value (Fetch API Key)
- Key: `API Key`
- From: `Config`

---

### Branch A: Google Gemini (`gemini-3.5-flash-lite`)

#### Action 18: If
- Input: `Dictionary Value` (from Action 16)
- Condition: **contains**
- Value: `Gemini`

#### Action 19: Get Contents of URL
- URL: `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`
- Method: **`POST`**
- Headers:
  - `Content-Type`: `application/json`
  - `X-goog-api-key`: Select variable `API Key` (from Action 17)
- Request Body: **JSON**
  - Add field `contents` (Array):
    - Item 1 (Dictionary):
      - `role` (Text): `user`
      - `parts` (Array):
        - Item 1 (Dictionary):
          - `text` (Text): `SystemPrompt` + `"\n\nSource Content:\n"` + `ExtractedContent`

#### Action 20: Get Dictionary Value
- Key: `candidates.1.content.parts.1.text`
- From: `Contents of URL` (from Action 19)

#### Action 21: Set Variable
- Variable Name: `GeneratedNote`
- Input: `Dictionary Value` (from Action 20)

---

### Branch B: ChatGPT / Claude / Other

#### Action 22: Otherwise
*(If user chose ChatGPT, Claude, or Other)*

1. **For ChatGPT**:
   - URL: `https://api.openai.com/v1/chat/completions`
   - Headers: `Authorization: Bearer [API Key]`
   - Body: `{"model": "gpt-4o-mini", "messages": [{"role": "system", "content": SystemPrompt}, {"role": "user", "content": ExtractedContent}]}`
   - Extract: `choices.1.message.content` ➔ Set to `GeneratedNote`
2. **For Claude**:
   - URL: `https://api.anthropic.com/v1/messages`
   - Headers: `x-api-key: [API Key]`, `anthropic-version: 2023-06-01`
   - Body: `{"model": "claude-3-5-haiku-latest", "max_tokens": 4096, "system": SystemPrompt, "messages": [{"role": "user", "content": ExtractedContent}]}`
   - Extract: `content.1.text` ➔ Set to `GeneratedNote`
3. **For Other**:
   - URL: `Config.Other URL`
   - Headers: `Authorization: Bearer [API Key]`
   - Body: `{"model": Config.Other Model, "messages": [{"role": "system", "content": SystemPrompt}, {"role": "user", "content": ExtractedContent}]}`
   - Extract: `choices.1.message.content` ➔ Set to `GeneratedNote`

*(End If for AI routing).*

---

## 7. Saving Note: Apple Notes vs. Files (Obsidian)

### Action 23: Get Dictionary Value
- Key: `Save Destination`
- From: `Config`

### Action 24: If
- Input: `Dictionary Value` (from Action 23)
- Condition: **contains**
- Value: `Apple Notes`

#### Action 25: Create Note (Apple Notes)
- Create note with: `GeneratedNote`
- In Folder: **`Retainer`** *(Make sure you created this folder in Apple Notes)*
- Expand dropdown: Turn **OFF** **Open When Run**.

### Action 26: Otherwise (Files / Obsidian)
1. **Match Text**: `(?<=#\s).*` in `GeneratedNote` (gets note title).
2. **Get First Match**: name variable `NoteTitle`.
3. **Replace Text**: Replace `[/\\?%*:|"<>.]` with empty text in `NoteTitle` to make it a safe filename.
4. **Save File**:
   - Input: `GeneratedNote`
   - Service: **iCloud Drive**
   - Subpath: `Obsidian/Vault/Retainer/[CleanedTitle].md`
   - Turn **OFF** **Ask Where to Save**.
   - Turn **ON** **Overwrite If File Exists**.

*(End If).*

---

## 8. Completion Notification

### Action 27: Show Notification
- Title: `Saved to Retainer`
- Body: `Note created and saved successfully!`

---

## 9. How to Share It

1. In the Shortcuts app, tap the **Share** button on the shortcut.
2. Click **Copy iCloud Link**.
3. Share the link with anyone! When they tap it, Apple's native setup wizard will prompt them for their provider and API key with your instructions.
