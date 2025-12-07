from flask import Flask, render_template, request, redirect, url_for
import requests
import json
import os
from datetime import datetime, date

app = Flask(__name__)

DATA_FILE = "data.json"

# Languages (codes must match the Free Dictionary API)
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

# Words to use for "Word of the Day"
WORD_OF_DAY_WORDS = [
    {"word": "sattva", "language": "sa"},     # Sanskrit
    {"word": "tamas", "language": "sa"},
    {"word": "rajas", "language": "sa"},
    {"word": "śiva", "language": "sa"},       # also try "shiva"
    {"word": "dharma", "language": "sa"},
    {"word": "karma", "language": "sa"},
    {"word": "bhakti", "language": "sa"},
    {"word": "śānti", "language": "sa"},
    {"word": "serene", "language": "en"},
    {"word": "benevolent", "language": "en"},
    {"word": "gratitude", "language": "en"},
    {"word": "सत्य", "language": "hi"},       # Hindi
    {"word": "शक्ति", "language": "hi"},
    {"word": "அன்பு", "language": "ta"},     # Tamil
    {"word": "அருள்", "language": "ta"}
]


def load_data():
    """Load favorites, notes, history, etc. from data.json"""
    if not os.path.exists(DATA_FILE):
        data = {
            "favorites": [],
            "pinned": [],
            "history": [],
            "general_notes": [],
            "word_notes": {}
        }
        save_data(data)
        return data

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    """Save favorites, notes, history, etc. to data.json"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_word_info(word, language_code):
    """
    Look up a word in many languages using FreeDictionaryAPI.com.

    Docs: https://freedictionaryapi.com
    Endpoint pattern:
      GET https://freedictionaryapi.com/api/v1/entries/{language}/{word}?translations=true
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
    #   "word": "sattva",
    #   "entries": [...],
    #   "source": { "url": "...", "license": { ... } }
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

            # Translations (optional)
            for t in sense.get("translations", []):
                t_lang = t.get("language", {})
                all_translations.append({
                    "language_code": t_lang.get("code"),
                    "language_name": t_lang.get("name"),
                    "word": t.get("word")
                })

    return {
        "word": word_text,
        "definitions": all_definitions,
        "examples": all_examples,
        "synonyms": list(all_synonyms),
        "translations": all_translations,
        "source_url": source_url
    }


def get_word_of_the_day():
    """
    Pick one word from WORD_OF_DAY_WORDS based on today's date,
    and fetch its info using get_word_info.
    """
    if not WORD_OF_DAY_WORDS:
        return None

    today = date.today()
    index = today.toordinal() % len(WORD_OF_DAY_WORDS)
    entry = WORD_OF_DAY_WORDS[index]

    word = entry["word"]
    language_code = entry["language"]

    info = get_word_info(word, language_code)

    # Find a pretty language label for display (e.g. "Sanskrit" instead of "sa")
    language_label = language_code
    for lang in LANGUAGE_OPTIONS:
        if lang["code"] == language_code:
            language_label = lang["label"]
            break

    # Get a short preview definition if possible
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


@app.route("/", methods=["GET"])
def home():
    data = load_data()
    history = data["history"][:20]  # last 20 searches
    favorites = data["favorites"]
    pinned = data["pinned"]

    word_of_the_day = get_word_of_the_day()

    return render_template(
        "home.html",
        history=history,
        favorites=favorites,
        pinned=pinned,
        languages=LANGUAGE_OPTIONS,
        selected_language=DEFAULT_LANGUAGE,
        word_of_the_day=word_of_the_day,
    )


@app.route("/search", methods=["GET", "POST"])
def search():
    data = load_data()

    if request.method == "POST":
        word = request.form.get("word", "").strip()
        language = request.form.get("language", DEFAULT_LANGUAGE).strip() or DEFAULT_LANGUAGE
        if not word:
            return redirect(url_for("home"))
        # Redirect to GET with query parameters
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

    return render_template(
        "word.html",
        word=word,
        info=info,
        is_favorite=is_favorite,
        is_pinned=is_pinned,
        word_notes=word_notes_sorted,
        languages=LANGUAGE_OPTIONS,
        selected_language=language,
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


if __name__ == "__main__":
    # debug=True is handy while developing
    app.run(debug=True)
