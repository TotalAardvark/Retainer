import os
import plistlib
import subprocess
from pathlib import Path

def build_retainer_shortcut():
    prompt_text = """You are an expert cognitive scientist, technical analyst, and spaced-repetition flashcard author.
Analyze the provided source content and output a clean note matching this exact structure:

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
**Q2: ...**"""

    actions = [
        # Action 0: Config Dictionary
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.dictionary",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_CONFIG_DICT",
                "WFItems": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "AI Provider"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {"Value": {"string": "Google Gemini"}, "WFSerializationType": "WFTextTokenString"},
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "API Key"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {"Value": {"string": ""}, "WFSerializationType": "WFTextTokenString"},
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "Save Destination"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {"Value": {"string": "Apple Notes"}, "WFSerializationType": "WFTextTokenString"},
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "Other URL"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {"Value": {"string": "https://openrouter.ai/api/v1/chat/completions"}, "WFSerializationType": "WFTextTokenString"},
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "Other Model"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {"Value": {"string": "meta-llama/llama-3.3-70b-instruct:free"}, "WFSerializationType": "WFTextTokenString"},
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "Vault Path"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {"Value": {"string": "Obsidian/Vault/Retainer"}, "WFSerializationType": "WFTextTokenString"},
                            },
                        ]
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # Action 1: Set Variable Config
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": "Config",
                "WFInput": {
                    "Value": {
                        "OutputUUID": "ACTION_CONFIG_DICT",
                        "Type": "ActionOutput",
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 2: Store System Prompt in variable
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_PROMPT_TEXT",
                "WFTextActionText": prompt_text,
            },
        },
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": "SystemPrompt",
                "WFInput": {
                    "Value": {
                        "OutputUUID": "ACTION_PROMPT_TEXT",
                        "Type": "ActionOutput",
                    },
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 4: Check if Shortcut Input contains 'youtu'
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": "COND_IS_YOUTUBE",
                "WFCondition": 99,  # contains
                "WFConditionalActionString": "youtu",
                "WFControlFlowMode": 0,
                "WFInput": {
                    "Type": "ExtensionInput",
                },
            },
        },
        # Action 5: Match Video ID regex
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.text.match",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_MATCH_VIDEOID",
                "WFMatchTextPattern": r"(?<=v=|\/)([0-9A-Za-z_-]{11})",
                "text": {
                    "Value": {"Type": "ExtensionInput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 6: Get First Match
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getitemfromlist",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_FIRST_VIDEOID",
                "WFItemSpecifier": "First Item",
                "WFInput": {
                    "Value": {"OutputUUID": "ACTION_MATCH_VIDEOID", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 7: Post to InnerTube player endpoint
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_INNERTUBE_RESP",
                "WFURL": "https://www.youtube.com/youtubei/v1/player",
                "WFHTTPMethod": "POST",
                "WFHTTPBodyType": "JSON",
                "WFJSONValues": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "videoId"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {
                                    "Value": {
                                        "attachmentsByRange": {
                                            "{0, 1}": {"OutputUUID": "ACTION_FIRST_VIDEOID", "Type": "ActionOutput"}
                                        },
                                        "string": "\ufffc",
                                    },
                                    "WFSerializationType": "WFTextTokenString",
                                },
                            },
                            {
                                "WFItemType": 1,
                                "WFKey": {"Value": {"string": "context"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {
                                    "Value": {
                                        "WFDictionaryFieldValueItems": [
                                            {
                                                "WFItemType": 1,
                                                "WFKey": {"Value": {"string": "client"}, "WFSerializationType": "WFTextTokenString"},
                                                "WFValue": {
                                                    "Value": {
                                                        "WFDictionaryFieldValueItems": [
                                                            {
                                                                "WFItemType": 0,
                                                                "WFKey": {"Value": {"string": "clientName"}, "WFSerializationType": "WFTextTokenString"},
                                                                "WFValue": {"Value": {"string": "ANDROID"}, "WFSerializationType": "WFTextTokenString"},
                                                            },
                                                            {
                                                                "WFItemType": 0,
                                                                "WFKey": {"Value": {"string": "clientVersion"}, "WFSerializationType": "WFTextTokenString"},
                                                                "WFValue": {"Value": {"string": "20.10.38"}, "WFSerializationType": "WFTextTokenString"},
                                                            },
                                                        ]
                                                    },
                                                    "WFSerializationType": "WFDictionaryFieldValue",
                                                },
                                            }
                                        ]
                                    },
                                    "WFSerializationType": "WFDictionaryFieldValue",
                                },
                            },
                        ]
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # Action 8: Extract baseUrl
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_GET_BASEURL",
                "WFDictionaryKey": "captions.playerCaptionsTracklistRenderer.captionTracks.1.baseUrl",
                "WFInput": {
                    "Value": {"OutputUUID": "ACTION_INNERTUBE_RESP", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 9: Download XML subtitles
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_XML_CAPTIONS",
                "WFURL": {
                    "Value": {
                        "attachmentsByRange": {
                            "{0, 1}": {"OutputUUID": "ACTION_GET_BASEURL", "Type": "ActionOutput"}
                        },
                        "string": "\ufffc",
                    },
                    "WFSerializationType": "WFTextTokenString",
                },
            },
        },
        # Action 10: Extract subtitle text via regex
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.text.match",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_MATCH_XML_TEXT",
                "WFMatchTextPattern": r"(?<=<text[^>]*>)([\s\S]*?)(?=<\/text>)|(?<=<p[^>]*>)([\s\S]*?)(?=<\/p>)",
                "text": {
                    "Value": {"OutputUUID": "ACTION_XML_CAPTIONS", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 11: Combine subtitle lines with space
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.text.combine",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_COMBINED_TRANSCRIPT",
                "WFTextSeparator": "Custom",
                "WFTextCustomSeparator": " ",
                "text": {
                    "Value": {"OutputUUID": "ACTION_MATCH_XML_TEXT", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 12: Set ExtractedContent for YouTube
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": "ExtractedContent",
                "WFInput": {
                    "Value": {"OutputUUID": "ACTION_COMBINED_TRANSCRIPT", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 13: Otherwise (Web Article)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": "COND_IS_YOUTUBE",
                "WFControlFlowMode": 1,
            },
        },
        # Action 14: Download Article via Jina Reader
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_JINA_ARTICLE",
                "WFURL": {
                    "Value": {
                        "attachmentsByRange": {
                            "{17, 1}": {"Type": "ExtensionInput"}
                        },
                        "string": "https://r.jina.ai/\ufffc",
                    },
                    "WFSerializationType": "WFTextTokenString",
                },
                "WFHTTPHeaders": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "Accept"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {"Value": {"string": "text/plain"}, "WFSerializationType": "WFTextTokenString"},
                            }
                        ]
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # Action 15: Set ExtractedContent for Article
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": "ExtractedContent",
                "WFInput": {
                    "Value": {"OutputUUID": "ACTION_JINA_ARTICLE", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 16: End If (YouTube branch)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": "COND_IS_YOUTUBE",
                "WFControlFlowMode": 2,
            },
        },
        # Action 17: Get AI Provider from Config
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_GET_PROVIDER",
                "WFDictionaryKey": "AI Provider",
                "WFInput": {
                    "Value": {"VariableName": "Config", "Type": "Variable"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 18: Get API Key from Config
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_GET_APIKEY",
                "WFDictionaryKey": "API Key",
                "WFInput": {
                    "Value": {"VariableName": "Config", "Type": "Variable"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 19: Check if AI Provider contains Gemini
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": "COND_AI_PROVIDER",
                "WFCondition": 99,
                "WFConditionalActionString": "Gemini",
                "WFControlFlowMode": 0,
                "WFInput": {
                    "Value": {"OutputUUID": "ACTION_GET_PROVIDER", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 20: Call Google Gemini REST API
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_GEMINI_RESP",
                "WFURL": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
                "WFHTTPMethod": "POST",
                "WFHTTPHeaders": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "Content-Type"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {"Value": {"string": "application/json"}, "WFSerializationType": "WFTextTokenString"},
                            },
                            {
                                "WFItemType": 0,
                                "WFKey": {"Value": {"string": "X-goog-api-key"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {
                                    "Value": {
                                        "attachmentsByRange": {
                                            "{0, 1}": {"OutputUUID": "ACTION_GET_APIKEY", "Type": "ActionOutput"}
                                        },
                                        "string": "\ufffc",
                                    },
                                    "WFSerializationType": "WFTextTokenString",
                                },
                            },
                        ]
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
                "WFHTTPBodyType": "JSON",
                "WFJSONValues": {
                    "Value": {
                        "WFDictionaryFieldValueItems": [
                            {
                                "WFItemType": 2,
                                "WFKey": {"Value": {"string": "contents"}, "WFSerializationType": "WFTextTokenString"},
                                "WFValue": {
                                    "Value": {
                                        "WFDictionaryFieldValueItems": [
                                            {
                                                "WFItemType": 1,
                                                "WFKey": {"Value": {"string": "0"}, "WFSerializationType": "WFTextTokenString"},
                                                "WFValue": {
                                                    "Value": {
                                                        "WFDictionaryFieldValueItems": [
                                                            {
                                                                "WFItemType": 0,
                                                                "WFKey": {"Value": {"string": "role"}, "WFSerializationType": "WFTextTokenString"},
                                                                "WFValue": {"Value": {"string": "user"}, "WFSerializationType": "WFTextTokenString"},
                                                            },
                                                            {
                                                                "WFItemType": 2,
                                                                "WFKey": {"Value": {"string": "parts"}, "WFSerializationType": "WFTextTokenString"},
                                                                "WFValue": {
                                                                    "Value": {
                                                                        "WFDictionaryFieldValueItems": [
                                                                            {
                                                                                "WFItemType": 1,
                                                                                "WFKey": {"Value": {"string": "0"}, "WFSerializationType": "WFTextTokenString"},
                                                                                "WFValue": {
                                                                                    "Value": {
                                                                                        "WFDictionaryFieldValueItems": [
                                                                                            {
                                                                                                "WFItemType": 0,
                                                                                                "WFKey": {"Value": {"string": "text"}, "WFSerializationType": "WFTextTokenString"},
                                                                                                "WFValue": {
                                                                                                    "Value": {
                                                                                                        "attachmentsByRange": {
                                                                                                            "{0, 1}": {"VariableName": "SystemPrompt", "Type": "Variable"},
                                                                                                            "{17, 1}": {"VariableName": "ExtractedContent", "Type": "Variable"},
                                                                                                        },
                                                                                                        "string": "\ufffc\n\nSource Content:\n\ufffc",
                                                                                                    },
                                                                                                    "WFSerializationType": "WFTextTokenString",
                                                                                                },
                                                                                            }
                                                                                        ]
                                                                                    },
                                                                                    "WFSerializationType": "WFDictionaryFieldValue",
                                                                                },
                                                                            }
                                                                        ]
                                                                    },
                                                                    "WFSerializationType": "WFDictionaryFieldValue",
                                                                },
                                                            },
                                                        ]
                                                    },
                                                    "WFSerializationType": "WFDictionaryFieldValue",
                                                },
                                            }
                                        ]
                                    },
                                    "WFSerializationType": "WFDictionaryFieldValue",
                                },
                            }
                        ]
                    },
                    "WFSerializationType": "WFDictionaryFieldValue",
                },
            },
        },
        # Action 21: Extract text from Gemini response
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_GEMINI_RESULT_TEXT",
                "WFDictionaryKey": "candidates.1.content.parts.1.text",
                "WFInput": {
                    "Value": {"OutputUUID": "ACTION_GEMINI_RESP", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 22: Set GeneratedNote
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.setvariable",
            "WFWorkflowActionParameters": {
                "WFVariableName": "GeneratedNote",
                "WFInput": {
                    "Value": {"OutputUUID": "ACTION_GEMINI_RESULT_TEXT", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 23: End If (AI Provider)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": "COND_AI_PROVIDER",
                "WFControlFlowMode": 2,
            },
        },
        # Action 24: Get Destination from Config
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
            "WFWorkflowActionParameters": {
                "UUID": "ACTION_GET_DESTINATION",
                "WFDictionaryKey": "Save Destination",
                "WFInput": {
                    "Value": {"VariableName": "Config", "Type": "Variable"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 25: Check if Save Destination is Apple Notes
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": "COND_DESTINATION",
                "WFCondition": 99,
                "WFConditionalActionString": "Apple Notes",
                "WFControlFlowMode": 0,
                "WFInput": {
                    "Value": {"OutputUUID": "ACTION_GET_DESTINATION", "Type": "ActionOutput"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 26: Create Apple Note
        {
            "WFWorkflowActionIdentifier": "com.apple.mobilenotes.SharingExtension",
            "WFWorkflowActionParameters": {
                "WFNoteText": {
                    "Value": {"VariableName": "GeneratedNote", "Type": "Variable"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
                "WFOpenWhenRun": False,
            },
        },
        # Action 27: Otherwise (Files / Obsidian)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": "COND_DESTINATION",
                "WFControlFlowMode": 1,
            },
        },
        # Action 28: Save File to iCloud Drive
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.documentpicker.save",
            "WFWorkflowActionParameters": {
                "WFAskWhereToSave": False,
                "WFSaveFileOverwrite": True,
                "WFFolder": "Retainer",
                "WFInput": {
                    "Value": {"VariableName": "GeneratedNote", "Type": "Variable"},
                    "WFSerializationType": "WFTextTokenAttachment",
                },
            },
        },
        # Action 29: End If (Destination)
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.conditional",
            "WFWorkflowActionParameters": {
                "GroupingIdentifier": "COND_DESTINATION",
                "WFControlFlowMode": 2,
            },
        },
        # Action 30: Show Notification
        {
            "WFWorkflowActionIdentifier": "is.workflow.actions.notification",
            "WFWorkflowActionParameters": {
                "WFNotificationActionTitle": "Saved to Retainer",
                "WFNotificationActionBody": "Note created successfully with flashcards and outline!",
            },
        },
    ]

    # Setup / Import Questions
    import_questions = [
        {
            "ActionIndex": 0,
            "Category": "Parameter",
            "ParameterKey": "WFDictionaryFieldValueItems",
            "Text": "Choose your AI Provider:\n• Google Gemini (Recommended - free API key in 10s at https://aistudio.google.com)\n• ChatGPT\n• Claude\n• Other",
            "DefaultValue": "Google Gemini",
        },
        {
            "ActionIndex": 0,
            "Category": "Parameter",
            "ParameterKey": "WFDictionaryFieldValueItems",
            "Text": "Enter your API Key:\n(If using Google Gemini, get your free key in 10 seconds with no credit card at: https://aistudio.google.com)",
            "DefaultValue": "",
        },
        {
            "ActionIndex": 0,
            "Category": "Parameter",
            "ParameterKey": "WFDictionaryFieldValueItems",
            "Text": "Where would you like to save your notes?\n• Apple Notes\n• Files",
            "DefaultValue": "Apple Notes",
        },
    ]

    workflow_dict = {
        "WFWorkflowClientRelease": "18.0",
        "WFWorkflowClientVersion": "1302.1.3",
        "WFWorkflowIcon": {
            "WFWorkflowIconStartColor": 4282601983,
            "WFWorkflowIconGlyphNumber": 59789,  # Brain / Book bookmark icon
        },
        "WFWorkflowImportQuestions": import_questions,
        "WFWorkflowInputContentItemClasses": ["WFURLContentItem", "WFTextContentItem"],
        "WFWorkflowMinimumClientVersion": 1300,
        "WFWorkflowMinimumClientVersionString": "1300",
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowTypes": ["ActionExtension"],
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowActions": actions,
    }

    out_dir = Path("/Users/pablo/Documents/antigravity/anki-generator/shortcuts_export")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "Retainer_unsigned.shortcut"
    signed_path = out_dir / "Save to Retainer.shortcut"

    with open(raw_path, "wb") as f:
        plistlib.dump(workflow_dict, f, fmt=plistlib.FMT_BINARY)

    print("Unsigned shortcut created at:", raw_path)

    # Sign using macOS shortcuts CLI
    sign_res = subprocess.run(
        ["shortcuts", "sign", "--mode", "anyone", "-i", str(raw_path), "-o", str(signed_path)],
        capture_output=True,
        text=True,
    )
    print("Signing status code:", sign_res.returncode)
    if sign_res.returncode == 0:
        print("Signed shortcut ready at:", signed_path)
    else:
        print("Sign error:", sign_res.stderr)

if __name__ == "__main__":
    build_retainer_shortcut()
