from flask import Flask, render_template, request, redirect, url_for
import requests
import json
import os
from datetime import datetime, date

app = Flask(__name__)

DATA_FILE = "data.json"

# Languages (codes must match the dictionary API)
LANGUAGE_OPTIONS = [
    {"code": "en", "label": "English"},
    {"code": "hi", "label": "Hindi"},
    {"code": "sa", "label": "Sanskrit"},
    {"code": "ta", "label": "Tamil"},
    {"code": "es", "label": "Spanish"},
    {"code": "fr", "label": "French"},
    {"code": "de", "label": "German"},
    {"code": "all", "label": "All languages (advanced)"}
]

DEFAULT_LANGUAGE = "en"

# ---------- WORD LISTS ----------

# Non-Sanskrit words for Word of the Day
WORD_OF_DAY_WORDS = [
    {"word": "serene", "language": "en"},
    {"word": "benevolent", "language": "en"},
    {"word": "gratitude", "language": "en"},
    {"word": "resilient", "language": "en"},
    {"word": "empathy", "language": "en"},
    {"word": "सत्य", "language": "hi"},       # Hindi
    {"word": "शक्ति", "language": "hi"},
    {"word": "आनंद", "language": "hi"},
    {"word": "அன்பு", "language": "ta"},     # Tamil: love
    {"word": "அருள்", "language": "ta"},     # Tamil: grace
    {"word": "மெய்ப்பு", "language": "ta"}    # Tamil: truth / reality
]

# Sanskrit study words (shown in a separate section)
SANSKRIT_STUDY_WORDS = [
    {"word": "sattva", "language": "sa"},
    {"word": "tamas", "language": "sa"},
    {"word": "rajas", "language": "sa"},
    {"word": "śiva", "language": "sa"},
    {"word": "dharma", "language": "sa"},
    {"word": "karma", "language": "sa"},
    {"word": "bhakti", "language": "sa"},
    {"word": "śānti", "language": "sa"},
    {"word": "ātman", "language": "sa"},
    {"word": "prakṛti", "language": "sa"},
    {"word": "puruṣa", "language": "sa"}
]


# ---------- DATA LOAD / SAVE ----------

def load_data():
    """Load favorites, notes, history, etc. from data.json"""
    if not os.path.exists(DATA_FILE):
        data = {
            "favorites": [],
            "pinned": [],
            "history": [],
            "general_notes": [],
            "word_notes": {},
            "word_tags": {}   # tags for words
        }
        save_data(data)
        return data

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Backwards compatibility: if old data.json has no word_tags
    if "word_tags" not in data:
        data["word_tags"] = {}
        save_data(data)

    return data


def save_data(data):
    """Save favorites, notes, history, etc. to data.json"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------- DICTIONARY LOOKUP (WEB API) ----------

def get_word_info(word, language_code):
    """
    Look up a word using an online dictionary API (Wiktionary-based style).
    All definitions come from the API, not from hand-written text.
    """
    base_url = "https://freedictionaryapi.com/api/v1/entries"
    url = f"{base_url}/{language_code}/{word}?translations=true"

    try:
        response = requests.get(url, timeout=10)
    except Exception:
        return None

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    # Expected main shape:
    # {
    #   "word": "...",
    #   "entries": [...],
    #   "source": { "url": "...", ... }
    # }

    word_text = data.get("word", word)
    entries = data.get("entries", [])
    source = data.get("source", {})
    source_url = source.get("url")

    all_definitions = []
    all_examples = []
    all_synonyms = set()
    all_translations = []

    for entry in entries:
        lang_info = entry.get("language", {})
        lang_code = lang_info.get("code")
        lang_name = lang_info.get("name")
        part_of_speech = entry.get("partOfSpeech", "")

        # Entry-level synonyms
        for s in entry.get("synonyms", []):
            all_synonyms.add(s)

        senses = entry.get("senses", [])
        for sense in senses:
            definition_text = sense.get("definition", "")

            all_definitions.append({
                "part_of_speech": part_of_speech,
                "definition": definition_text,
                "language_code": lang_code,
                "language_name": lang_name,
            })

            # Examples
            for ex in sense.get("examples", []):
                all_examples.append(ex)

            # Sense-level synonyms
            for s in sense.get("synonyms", []):
                all_synonyms.add(s)

            # Optional translations
            for t in sense.get("translations", []):
                t_lang = t.get("language", {})
                all_translations.append({
                    "language_code": t_lang.get("code"),
                    "language_name": t_lang.get("name"),
                    "word": t.get("word")
                })

    if not all_definitions:
        return None

    return {
        "word": word_text,
        "definitions": all_definitions,
        "examples": all_examples,
        "synonyms": list(all_synonyms),
        "translations": all_translations,
        "source_url": source_url
    }


# ---------- WORD OF THE DAY + SANSKRIT STUDY WORD ----------

def get_word_of_the_day():
    """
    Pick one non-Sanskrit word from WORD_OF_DAY_WORDS based on today's date.
    """
    if not WORD_OF_DAY_WORDS:
        return None

    today = date.today()
    index = today.toordinal() % len(WORD_OF_DAY_WORDS)
    entry = WORD_OF_DAY_WORDS[index]

    word = entry["word"]
    language_code = entry["language"]

    info = get_word_info(word, language_code)

    # Find a user-friendly language label
    language_label = language_code
    for lang in LANGUAGE_OPTIONS:
        if lang["code"] == language_code:
            language_label = lang["label"]
            break

    short_definition = None
    if info and info.get("definitions"):
        first_def = info["definitions"][0]
        short_definition = first_def.get("definition")

    return {
        "word": word,
        "language_code": language_code,
        "language_label": language_label,
        "short_definition": short_definition
    }


def get_sanskrit_study_word():
    """
    Pick one Sanskrit word from SANSKRIT_STUDY_WORDS based on today's date.
    This is shown in a separate section so you can learn Sanskrit terms separately.
    """
    if not SANSKRIT_STUDY_WORDS:
        return None

    today = date.today()
    index = today.toordinal() % len(SANSKRIT_STUDY_WORDS)
    entry = SANSKRIT_STUDY_WORDS[index]

    word = entry["word"]
    language_code = entry["language"]  # should be "sa"

    info = get_word_info(word, language_code)

    # language_label should be "Sanskrit"
    language_label = language_code
    for lang in LANGUAGE_OPTIONS:
        if lang["code"] == language_code:
            language_label = lang["label"]
            break

    short_definition = None
    if info and info.get("definitions"):
        first_def = info["definitions"][0]
        short_definition = first_def.get("definition")

    return {
        "word": word,
        "language_code": language_code,
        "language_label": language_label,
        "short_definition": short_definition
    }


# ---------- ROUTES ----------

@app.route("/", methods=["GET"])
def home():
    data = load_data()
    history = data["history"][:20]  # last 20 searches
    favorites = data["favorites"]
    pinned = data["pinned"]

    word_of_the_day = get_word_of_the_day()
    sanskrit_study_word = get_sanskrit_study_word()

    return render_template(
        "home.html",
        history=history,
        favorites=favorites,
        pinned=pinned,
        languages=LANGUAGE_OPTIONS,
        selected_language=DEFAULT_LANGUAGE,
        word_of_the_day=word_of_the_day,
        sanskrit_study_word=sanskrit_study_word,
    )


@app.route("/search", methods=["GET", "POST"])
def search():
    data = load_data()

    if request.method == "POST":
        word = request.form.get("word", "").strip()
        language = request.form.get("language", DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
        if not word:
            return redirect(url_for("home"))
        return redirect(url_for("search", word=word, language=language))

    # GET request (after redirect)
    word = request.args.get("word", "").strip()
    language = request.args.get("language", DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE

    if not word:
        return redirect(url_for("home"))

    info = get_word_info(word, language)

    # Update history: newest first, no duplicates
    if word in data["history"]:
        data["history"].remove(word)
    data["history"].insert(0, word)
    save_data(data)

    is_favorite = word in data["favorites"]
    is_pinned = word in data["pinned"]
    word_notes = data["word_notes"].get(word, [])
    word_notes_sorted = sorted(word_notes, key=lambda n: n["important"], reverse=True)

    # Tags for this word
    word_tags = data["word_tags"].get(word, [])

    return render_template(
        "word.html",
        word=word,
        info=info,
        is_favorite=is_favorite,
        is_pinned=is_pinned,
        word_notes=word_notes_sorted,
        languages=LANGUAGE_OPTIONS,
        selected_language=language,
        word_tags=word_tags,
    )


@app.route("/favorite/<language>/<word>")
def toggle_favorite(language, word):
    data = load_data()
    if word in data["favorites"]:
        data["favorites"].remove(word)
    else:
        data["favorites"].append(word)
    save_data(data)
    return redirect(url_for("search", word=word, language=language))


@app.route("/pin/<language>/<word>")
def toggle_pin(language, word):
    data = load_data()
    if word in data["pinned"]:
        data["pinned"].remove(word)
    else:
        data["pinned"].append(word)
    save_data(data)
    return redirect(url_for("search", word=word, language=language))


@app.route("/notes", methods=["GET", "POST"])
def notes():
    data = load_data()

    if request.method == "POST":
        text = request.form.get("note_text", "").strip()
        important = request.form.get("important") == "on"
        if text:
            note = {
                "id": int(datetime.now().timestamp()),
                "text": text,
                "important": important,
                "created_at": datetime.now().isoformat()
            }
            data["general_notes"].append(note)
            save_data(data)
        return redirect(url_for("notes"))

    # Sort notes: important first, then newest
    general_notes = sorted(
        data["general_notes"],
        key=lambda n: (not n["important"], -n["id"])
    )

    return render_template("notes.html", general_notes=general_notes)


@app.route("/notes/<int:note_id>/delete", methods=["POST"])
def delete_general_note(note_id):
    """Delete a general note by id."""
    data = load_data()
    data["general_notes"] = [n for n in data["general_notes"] if n["id"] != note_id]
    save_data(data)
    return redirect(url_for("notes"))


@app.route("/word/<language>/<word>/add_note", methods=["POST"])
def add_word_note(language, word):
    data = load_data()
    text = request.form.get("note_text", "").strip()
    important = request.form.get("important") == "on"

    if text:
        note = {
            "id": int(datetime.now().timestamp()),
            "text": text,
            "important": important,
            "created_at": datetime.now().isoformat()
        }
        if word not in data["word_notes"]:
            data["word_notes"][word] = []
        data["word_notes"][word].append(note)
        save_data(data)

    return redirect(url_for("search", word=word, language=language))


@app.route("/word/<language>/<word>/note/<int:note_id>/delete", methods=["POST"])
def delete_word_note(language, word, note_id):
    """Delete a word-specific note by id."""
    data = load_data()
    notes = data["word_notes"].get(word, [])
    notes = [n for n in notes if n["id"] != note_id]
    if notes:
        data["word_notes"][word] = notes
    else:
        # If no notes left for this word, remove the key entirely
        data["word_notes"].pop(word, None)
    save_data(data)
    return redirect(url_for("search", word=word, language=language))


@app.route("/word/<language>/<word>/add_tag", methods=["POST"])
def add_word_tag(language, word):
    data = load_data()
    tag_text = request.form.get("tag_text", "").strip()

    if tag_text:
        # Normalize tag: lower-case, collapse spaces
        normalized = " ".join(tag_text.lower().split())
        if normalized:
            if "word_tags" not in data:
                data["word_tags"] = {}
            if word not in data["word_tags"]:
                data["word_tags"][word] = []
            if normalized not in data["word_tags"][word]:
                data["word_tags"][word].append(normalized)
                save_data(data)

    return redirect(url_for("search", word=word, language=language))


# ---------- OVERALL SEARCH ROUTE ----------

@app.route("/search_all", methods=["GET", "POST"])
def search_all():
    data = load_data()

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        return redirect(url_for("search_all", q=query))

    query = request.args.get("q", "").strip()
    results = None

    if query:
        q = query.lower()

        # 1) Words from history, favorites, pinned, word_notes keys, word_tags keys
        word_candidates = set(data["history"]) | set(data["favorites"]) | set(data["pinned"])
        word_candidates |= set(data.get("word_notes", {}).keys())
        word_candidates |= set(data.get("word_tags", {}).keys())

        matching_words = sorted([w for w in word_candidates if q in w.lower()])

        # 2) General notes
        general_note_matches = [
            note for note in data["general_notes"]
            if q in note["text"].lower()
        ]

        # 3) Word-specific notes
        word_note_matches = []
        for w, notes in data.get("word_notes", {}).items():
            for note in notes:
                if q in note["text"].lower():
                    word_note_matches.append({
                        "word": w,
                        "note": note
                    })

        # 4) Tags
        tag_matches = []
        for w, tags in data.get("word_tags", {}).items():
            for t in tags:
                if q in t.lower():
                    tag_matches.append({
                        "word": w,
                        "tag": t
                    })

        results = {
            "words": matching_words,
            "general_notes": general_note_matches,
            "word_notes": word_note_matches,
            "tags": tag_matches,
        }

    return render_template(
        "search_all.html",
        query=query,
        results=results,
        default_language=DEFAULT_LANGUAGE,
    )


if __name__ == "__main__":
    app.run(debug=True)
