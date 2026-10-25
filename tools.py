import json
import os
from datetime import datetime, timedelta

import requests

import memory as mem

SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_time",
        "description": "Get the current local date and time.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for current or factual information.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "remember",
        "description": "Save a durable fact about the user when they ask you to remember something.",
        "parameters": {"type": "object", "properties": {
            "fact": {"type": "string", "description": "Short third-person fact, e.g. 'Birthday is March 4'"}},
            "required": ["fact"]}}},
    {"type": "function", "function": {
        "name": "forget",
        "description": "Delete saved facts containing this text, when the user asks you to forget something.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "add_reminder",
        "description": "Set a reminder that will be spoken aloud. Compute minutes from now using get_time if needed.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"},
            "minutes_from_now": {"type": "number"}},
            "required": ["text", "minutes_from_now"]}}},
    {"type": "function", "function": {
        "name": "list_reminders",
        "description": "List pending reminders.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "add_note",
        "description": "Save a note or to-do for the user.",
        "parameters": {"type": "object", "properties": {
            "text": {"type": "string"}}, "required": ["text"]}}},
    {"type": "function", "function": {
        "name": "read_notes",
        "description": "Read the user's saved notes and to-dos.",
        "parameters": {"type": "object", "properties": {}}}},
]


def _web_search(query):
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return "Web search isn't set up (missing TAVILY_API_KEY)."
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {key}"},
            json={"query": query, "max_results": 4, "include_answer": True},
            timeout=15,
        )
        r.raise_for_status()
        d = r.json()
    except Exception as e:  # network/API failure should not crash the agent
        return f"Search failed: {e}"
    parts = []
    if d.get("answer"):
        parts.append("Answer: " + d["answer"])
    for x in d.get("results", [])[:4]:
        parts.append(f"- {x.get('title')}: {(x.get('content') or '')[:300]}")
    return "\n".join(parts) or "No results."


def run(name, args, memory):
    try:
        if name == "get_time":
            return datetime.now().strftime("%A, %d %B %Y, %I:%M %p")
        if name == "web_search":
            return _web_search(args.get("query", ""))
        if name == "remember":
            return "Saved." if memory.add(args.get("fact", "")) else "Already knew that."
        if name == "forget":
            return f"Removed {memory.forget(args.get('text', ''))} item(s)."
        if name == "add_reminder":
            due = datetime.now() + timedelta(minutes=float(args["minutes_from_now"]))
            items = mem.load_json("reminders.json", [])
            items.append({"text": args["text"], "due": due.isoformat(timespec="seconds")})
            mem.save_json("reminders.json", items)
            return f"Reminder set for {due.strftime('%I:%M %p')}."
        if name == "list_reminders":
            items = mem.load_json("reminders.json", [])
            return "\n".join(f"{i['due']}: {i['text']}" for i in items) or "No pending reminders."
        if name == "add_note":
            notes = mem.load_json("notes.json", [])
            notes.append({"text": args["text"], "ts": datetime.now().isoformat(timespec="seconds")})
            mem.save_json("notes.json", notes)
            return "Noted."
        if name == "read_notes":
            notes = mem.load_json("notes.json", [])
            return "\n".join(f"- {n['text']}" for n in notes) or "No notes."
    except Exception as e:
        return f"Tool error: {e}"
    return f"Unknown tool {name}."


def pop_due_reminders():
    """Return reminder texts that are due and remove them from disk."""
    items = mem.load_json("reminders.json", [])
    now = datetime.now()
    due = [i for i in items if datetime.fromisoformat(i["due"]) <= now]
    if due:
        mem.save_json("reminders.json", [i for i in items if i not in due])
    return [i["text"] for i in due]
